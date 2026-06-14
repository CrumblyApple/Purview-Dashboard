"""
Rasterises OSM building footprint polygons into a per-pixel coverage
fraction channel for the dasymetric CNN input stack.
 
Output: data/ml/features/building_footprints_20{year}.tif
        Float32, values 0.0-1.0 — fraction of each pixel's area
        covered by building footprints.
 
Source: Geofabrik historical OSM PBF snapshots, extracted with osmium
        and converted to GeoPackage via ogr2ogr.
 
PBF snapshots are downloaded once per year and cached locally.
The PBF (~2-3 GB) can be deleted after extraction to save disk space.
 
Dependencies:
    sudo apt install osmium-tool gdal-bin
"""
 
import logging
import subprocess
from pathlib import Path
 
import geopandas as gpd
import httpx
import numpy as np
from rasterio import features as rio_features
from rasterio.transform import from_bounds as _from_bounds
from shapely.geometry import box
from shapely.strtree import STRtree

from ...spatial.rasterise import NATIONAL_GRID, GridDef, write_cog
 
log = logging.getLogger(__name__)
 
CACHE_DIR = Path("data/raw/osm_cache/buildings")
OUTPUT_DIR = Path("data/ml/features")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
 
# Geofabrik historical files 
HISTORICAL_PBFS: dict[int, str] = {
    21: "https://download.geofabrik.de/australia-oceania/australia-210101.osm.pbf",
    22: "https://download.geofabrik.de/australia-oceania/australia-220101.osm.pbf",
    23: "https://download.geofabrik.de/australia-oceania/australia-230101.osm.pbf",
    24: "https://download.geofabrik.de/australia-oceania/australia-240101.osm.pbf",
    25: "https://download.geofabrik.de/australia-oceania/australia-250101.osm.pbf",
    26: "https://download.geofabrik.de/australia-oceania/australia-260101.osm.pbf",
}

# Non-habitable buildings
EXCLUDE_BUILDING_TYPES = {
    "shed", "garage", "garages", "carport", "ruins", "silo", "greenhouse", "barn", "hangar", "hut"
}

# Rasterisation defaults
DEFAULT_TILE_SIZE   = 1024   # output pixels per tile side
DEFAULT_FACTOR      = 4      # supersampling factor (~62m subpixels at 250m grid)



# Fetch data
def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
 
    with httpx.stream("GET", url, follow_redirects=True, timeout=3600) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
 
    log.info("Download complete → %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)


def _check_dependencies() -> None:
    for tool in ("osmium", "ogr2ogr"):
        result = subprocess.run(["which", tool], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"'{tool}' not found")
 

# PBF to GeoPackage
def extract_buildings_from_pbf(pbf_path: Path, out_path: Path) -> Path:
    _check_dependencies()
 
    filtered_pbf = pbf_path.with_suffix(".buildings.osm.pbf")
 
    log.info("Filtering buildings from PBF…")
    subprocess.run([
        "osmium", "tags-filter",
        str(pbf_path),
        "w/building",
        "r/building",
        "-o", str(filtered_pbf),
        "--overwrite",
    ], check=True)
 
    log.info(
        "Filtered PBF: %.1f MB",
        filtered_pbf.stat().st_size / 1e6,
    )
 
    log.info("Converting to GeoPackage via ogr2ogr…")
    subprocess.run([
        "ogr2ogr",
        "-f", "GPKG",
        str(out_path),
        str(filtered_pbf),
        "multipolygons",
        "-where", "building IS NOT NULL",
        "-overwrite",
    ], check=True)
 
    filtered_pbf.unlink()
    log.info("Extracted buildings → %s", out_path.name)
 
    return out_path
 

# Pipeline function to fetch and cache data
def fetch_buildings(year: int = 25, force: bool = False) -> gpd.GeoDataFrame:
    gpkg_path = CACHE_DIR / f"buildings_20{year}.gpkg"
    pbf_path = CACHE_DIR / f"australia_20{year}.osm.pbf"
 
    if gpkg_path.exists() and not force:
        log.info("Cache hit: %s", gpkg_path.name)
        gdf = gpd.read_file(gpkg_path)
        log.info("Loaded %d building footprints for 20%d", len(gdf), year)
        return gdf[["geometry"]].reset_index(drop=True)
 
    if not pbf_path.exists():
        url = HISTORICAL_PBFS.get(year)
        if url is None:
            raise ValueError(
                f"No PBF URL configured for year 20{year}. "
                f"Add an entry to HISTORICAL_PBFS."
            )
        _download_file(url, pbf_path)
 
    extract_buildings_from_pbf(pbf_path, gpkg_path)
    gdf = gpd.read_file(gpkg_path)
 
    # Filter geometry types
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
 
    # Remove non-habitable structures
    if "building" in gdf.columns:
        before = len(gdf)
        gdf = gdf[~gdf["building"].isin(EXCLUDE_BUILDING_TYPES)]
        log.info(
            "Filtered non-habitable: %d → %d buildings",
            before, len(gdf),
        )
 
    # Ensure EPSG:4326
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
 
    gdf = gdf[["geometry"]].reset_index(drop=True)
    log.info("Loaded %d building footprints for 20%d", len(gdf), year)
    return gdf
 

# Rasterise: subsampled at 25mx25m scale (binary), then downscaled to 250mx250m (fractions)
def _supersample_factor(grid: GridDef, target_subpixel_m: float = 25.0) -> int:
    pixel_size_m = grid.resolution * 111_320
    factor = max(1, round(pixel_size_m / target_subpixel_m))
    log.info(
        "Supersample factor: %d (pixel=%.0fm → subpixel=%.0fm)",
        factor, pixel_size_m, pixel_size_m / factor,
    )
    return factor

# Returns pixels with value indicating percentage covered
def rasterise_coverage_fraction(
    gdf:   gpd.GeoDataFrame,
    year:  int = 25,
    grid:  GridDef = NATIONAL_GRID,
    force: bool = False,
    tile_size: int = DEFAULT_TILE_SIZE,
    factor: int = DEFAULT_FACTOR
) -> np.ndarray:
    out_path = OUTPUT_DIR / f"building_footprints_20{year}.tif"
 
    if out_path.exists() and not force:
        log.info("Loading cached coverage raster: %s", out_path.name)
        import rasterio
        with rasterio.open(out_path) as src:
            return src.read(1)
 
    pixel_size_m = grid.resolution * 111_320
    log.info(
        "Rasterising %d buildings | tile=%dpx | factor=%d | subpixel=%.0fm",
        len(gdf), tile_size, factor, pixel_size_m / factor,
    )
 
    # Build spatial index once over all building geometries
    tree = STRtree(gdf.geometry.values)
 
    coverage   = np.zeros((grid.height, grid.width), dtype=np.float32)
    n_tiles_y  = int(np.ceil(grid.height / tile_size))
    n_tiles_x  = int(np.ceil(grid.width  / tile_size))
    total      = n_tiles_y * n_tiles_x
    done       = 0
 
    for ty in range(n_tiles_y):
        for tx in range(n_tiles_x):
 
            # Output pixel bounds
            row_start = ty * tile_size
            row_end   = min(row_start + tile_size, grid.height)
            col_start = tx * tile_size
            col_end   = min(col_start + tile_size, grid.width)
 
            tile_h = row_end - row_start
            tile_w = col_end - col_start
 
            # Geographic bounds of this tile
            left   = grid.left + col_start * grid.resolution
            right  = grid.left + col_end   * grid.resolution
            top    = grid.top  - row_start * grid.resolution
            bottom = grid.top  - row_end   * grid.resolution
 
            # Supersampled affine transform for this tile
            super_transform = _from_bounds(
                left, bottom, right, top,
                tile_w * factor, tile_h * factor,
            )
 
            # Query spatial index for buildings intersecting this tile
            tile_box   = box(left, bottom, right, top)
            candidate_idx = tree.query(tile_box)
            tile_geoms = gdf.geometry.iloc[candidate_idx]
            tile_geoms = tile_geoms[tile_geoms.intersects(tile_box)]
 
            # Rasterise tile at supersampled resolution
            super_mask = np.zeros(
                (tile_h * factor, tile_w * factor), dtype=np.uint8,
            )
 
            if len(tile_geoms) > 0:
                shapes = (
                    (geom, 1)
                    for geom in tile_geoms
                    if geom is not None and geom.is_valid
                )
                rio_features.rasterize(
                    shapes=shapes,
                    out=super_mask,
                    transform=super_transform,
                    fill=0,
                    all_touched=False,
                    dtype=np.uint8,
                )
 
            # Downsample by block-averaging → coverage fraction
            coverage[row_start:row_end, col_start:col_end] = (
                super_mask
                .reshape(tile_h, factor, tile_w, factor)
                .astype(np.float32)
                .mean(axis=(1, 3))
            )
 
            done += 1
            if done % 50 == 0 or done == total:
                log.info(
                    "  Tile %d / %d (%.0f%%)",
                    done, total, 100 * done / total,
                )
 
    log.info(
        "Coverage complete: mean=%.4f  max=%.4f  non-zero=%d / %d pixels",
        coverage.mean(), coverage.max(),
        (coverage > 0).sum(), coverage.size,
    )
 
    write_cog(
        coverage, out_path, grid=grid, nodata=None,
        band_name=f"building_coverage_fraction_20{year}",
    )
    return coverage

 
# Pipeline entry point
def build_building_footprint_channel(
    year: int = 25,
    grid: GridDef = NATIONAL_GRID,
    force: bool = False,
    tile_size: int = DEFAULT_TILE_SIZE,
    factor: int = DEFAULT_FACTOR
) -> np.ndarray:
    out_path = OUTPUT_DIR / f"building_footprints_20{year}.tif"
 
    if out_path.exists() and not force:
        log.info("Channel already exists: %s", out_path.name)
        import rasterio
        with rasterio.open(out_path) as src:
            return src.read(1)
 
    buildings = fetch_buildings(year=year, force=force)
    return rasterise_coverage_fraction(
        buildings, year=year, grid=grid, force=force,
        tile_size=tile_size, factor=factor,
    )
 

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
 
    year      = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    force     = "--force" in sys.argv
    tile_size = int(next(
        (a.split("=")[1] for a in sys.argv if a.startswith("--tile-size=")),
        DEFAULT_TILE_SIZE,
    ))
    factor    = int(next(
        (a.split("=")[1] for a in sys.argv if a.startswith("--factor=")),
        DEFAULT_FACTOR,
    ))
 
    coverage = build_building_footprint_channel(
        year=year, force=force, tile_size=tile_size, factor=factor,
    )
 
    print(f"\nBuilding coverage channel (20{year}): {coverage.shape}")
    print(f"  Range:     {coverage.min():.4f} → {coverage.max():.4f}")
    print(f"  Mean:      {coverage.mean():.4f}")
    print(f"  Non-zero:  {(coverage > 0).sum():,} / {coverage.size:,} pixels")
    print(f"  Output:    {OUTPUT_DIR}/building_footprints_20{year}.tif")