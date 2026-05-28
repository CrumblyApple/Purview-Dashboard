'''
    Convert vector data into a raster grid
    Outputs Cloud-Optimised GeoTiff (COG)
'''


import logging
from dataclasses import dataclass
from pathlib import Path
 
import geopandas as gpd
import numpy as np
import rasterio
from rasterio import features as rio_features
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
 
log = logging.getLogger(__name__)
 
OUTPUT_DIR = Path("data/outputs/rasters")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUSTRALIA_BOUNDS = {
    "left": 112.9,      # west
    "right": 153.7,     # east
    "top": -9.9,        # north
    "bottom": -43.7,    # south
}
 
RESOLUTION = 0.0025     # degrees, ~250m at Australian latitudes
CRS_EPSG = 7844         # GDA2020 geographic

@dataclass(frozen=True)
class GridDef:
    left: float
    right: float
    top: float
    bottom: float
    resolution: float
    epsg: int
 
    @property
    def width(self) -> int:
        return round((self.right - self.left) / self.resolution)
 
    @property
    def height(self) -> int:
        return round((self.top - self.bottom) / self.resolution)

    # Maps pixel coordinates to CRS coordinates
    @property
    def transform(self):
        return from_bounds(self.left, self.bottom, self.right, self.top, self.width, self.height)
 
    @property
    def crs(self) -> CRS:
        return CRS.from_epsg(self.epsg)
 
 
NATIONAL_GRID = GridDef(
    resolution=RESOLUTION,
    epsg=CRS_EPSG,
    **AUSTRALIA_BOUNDS
)

def rasterise_data(
    gdf: gpd.GeoDataFrame,
    target_col: str,
    grid: GridDef = NATIONAL_GRID,
    nodata: float = np.nan,                # Data written for NaN polygons
    all_touched: bool = False
) -> np.ndarray:
    if gdf.crs is None: raise ValueError("GeoDataFrame has no CRS set. Set it before rasterising")
 
    if gdf.crs.to_epsg() != grid.epsg:
        gdf = gdf.to_crs(epsg=grid.epsg)
 
    if target_col not in gdf.columns: raise KeyError(f"Column '{target_col}' not found")
 
    # Drop rows with null geometry or null values
    valid = gdf[gdf.geometry.notna() & gdf[target_col].notna()].copy()

    # rasterio.features.rasterize expects an iterable of (geometry, value) pairs
    shapes = ((geom, float(val)) for geom, val in zip(valid.geometry, valid[target_col]))
 
    out = np.full((grid.height, grid.width), fill_value=nodata, dtype=np.float32) # Empty output

    rio_features.rasterize(
        shapes=shapes,
        out=out,
        transform=grid.transform,
        fill=nodata,
        all_touched=all_touched,
        dtype=np.float32
    )
    return out

# Writes numpy array to 'Cloud-Optimised GeoTIFF'
# COG format requirements:
# - Tiled internally (256x256 tiles)
# - Overviews (pyramid levels) pre-computed     (downscaled copies for zooming)
# - LZW compression
def write_cog(
    array: np.ndarray,
    path: Path,
    grid: GridDef = NATIONAL_GRID,
    nodata: float = np.nan,
    band_name: str | None = None        # Optional band description
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
 
    if array.shape != (grid.height, grid.width): raise ValueError(f"Array shape mismatch")
 
    tmp_path = path.with_suffix(".tmp.tif") # TMP GeoTiff
 
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": nodata,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256
    }
 
    with rasterio.open(tmp_path, "w", **profile) as dest:
        dest.write(array, 1)
        if band_name:
            dest.update_tags(1, name=band_name)
 
    # Overviews
    overview_levels = [2, 4, 8, 16, 32]
    with rasterio.open(tmp_path, "r+") as dest:
        dest.build_overviews(overview_levels, Resampling.average)
        dest.update_tags(ns="rio_overview", resampling="average")
 
    # Write to COG
    cog_profile = {**profile, "copy_src_overviews": True}
    with rasterio.open(tmp_path, "r") as src:
        with rasterio.open(path, "w", **cog_profile) as dest:
            dest.write(src.read(1), 1)
            if band_name:
                dest.update_tags(1, name=band_name)
 
    tmp_path.unlink()
    log.info("COG written → %s (%.1f MB)", path, path.stat().st_size / 1e6)
    return path

# Pipeline elements
def rasterise_stat(
    gdf: gpd.GeoDataFrame,
    target_col: str,
    out_name: str,
    grid: GridDef = NATIONAL_GRID,
    nodata: float = np.nan
) -> Path:
    array = rasterise_data(gdf, target_col, grid=grid, nodata=nodata)
    out_path = OUTPUT_DIR / f"{out_name}.tif"
    return write_cog(array, out_path, grid=grid, nodata=nodata, band_name=target_col)

def rasterise_all_years(
    gdf: gpd.GeoDataFrame,
    target_col: str,
    year_col: str,
    out_prefix: str,
    grid: GridDef = NATIONAL_GRID
) -> dict[int, Path]:
    years = sorted(gdf[year_col].unique())
    results = {}
    for year in years:
        subset = gdf[gdf[year_col] == year].copy()
        out_name = f"{out_prefix}_{year}"
        path = rasterise_stat(subset, target_col, out_name, grid=grid)
        results[int(year)] = path
    return results

YEAR = "2025"

if __name__ == "__main__":
    import sys
    from . import gpkg_join as joiner
    from ..ingest.abs_ingest import ABSClient

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
 
    with ABSClient() as client:
        erp = client.fetch("erp_sa2")

    erp = erp[["ASGS_2021", "TIME_PERIOD", "value"]]
 
    log.info("ERP years available: %s", sorted(erp["TIME_PERIOD"].unique()))
 
    # Filter to target year
    erp_year = erp[erp["TIME_PERIOD"] == YEAR].copy()
    log.info("Rows for %s: %d", YEAR, len(erp_year))
 
    # Join + rasterise
    gdf = joiner.join_cross_section(
        erp_year,
        "erp",
        value_col="value"
    )
    log.info("Joined GeoDataFrame: %d rows, columns: %s", len(gdf), list(gdf.columns))
 
    out_path = rasterise_stat(
        gdf,
        target_col="value",
        out_name=f"erp_sa2_{YEAR}",
    )
    log.info("Done → %s", out_path)