'''
    2-Stage masking for population-related data
    
    1. Binary mask: exclusion with mesh block categories and data
    2. Weighted mask: based on GNAF address density (with mesh block fallback)
'''

import logging
from pathlib import Path
 
import pandas as pd
import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features as rio_features
from rasterio.transform import rowcol
 
from ..spatial.rasterise import NATIONAL_GRID, GridDef, write_cog
 
log = logging.getLogger(__name__)
 
OUTPUT_DIR = Path("data/outputs/masks")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
 
GPKG_PATH = Path("data/raw/asgs_3/ASGS_2021_Main_Structure_GDA2020.gpkg")
GNAF_PATH = Path("data/raw/gnaf/gnaf_core.parquet")

# Mesh block categories that can safely be excluded
MB_EXCLUDED: set[str] = {
    "Water",
    "Transport",
    "Parkland",
    "Primary Production",
    "Industrial",
    "Other"
}

FALLBACK_WEIGHTS: dict[str, float] = {
    "Residential": 1.0,
    "Commercial": 0.5,
    "Mixed Use": 0.5
}

# GNAF reliability that is strong enough for this use case (spatial precision)
GNAF_RELIABLE_CODES = {1, 2, 3}

def _load_mesh_blocks(gpkg_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(
        gpkg_path,
        layer="MB_2021_AUST_GDA2020",
        columns=["MB_CODE_2021", "MB_CATEGORY_2021", "SA2_CODE_2021", "geometry"],
    ).to_crs(epsg=7844)
    
    unknown = set(gdf["MB_CATEGORY_2021"].unique()) - MB_EXCLUDED - set(FALLBACK_WEIGHTS)
    if unknown: log.warning("Unknown MB categories excluded: %s", unknown)
    return gdf

def build_binary_mask(
    gpkg_path: Path = GPKG_PATH,
    grid: GridDef = NATIONAL_GRID,
    force: bool = False,                # Forcibly make new file
) -> np.ndarray:
    out_path = OUTPUT_DIR / "binary_mask.tif"
    if out_path.exists() and not force:
        with rasterio.open(out_path) as src:
            return src.read(1)
 
    gdf = _load_mesh_blocks(gpkg_path)
    excluded_gdf = gdf[gdf["MB_CATEGORY_2021"].isin(MB_EXCLUDED)]
 
    mask = np.zeros((grid.height, grid.width), dtype=np.uint8) # rasterize doesnt accept bools
    shapes = ((g, 1) for g in excluded_gdf.geometry if g is not None)
    rio_features.rasterize(
        shapes=shapes,
        out=mask,
        transform=grid.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
 
    write_cog(
        mask.astype(np.float32),
        out_path,
        grid=grid,
        nodata=None,
        band_name="exclusion_mask"
    )
    return mask

def _load_gnaf(gnaf_path: Path) -> np.ndarray:
    df = pd.read_parquet(gnaf_path)
    df = df.dropna(subset=["LONGITUDE", "LATITUDE"])
    return df["LONGITUDE"].to_numpy(), df["LATITUDE"].to_numpy()

# Creates a raster map of GNAF counts
def _bin_gnaf(
    lons: np.ndarray,
    lats: np.ndarray,
    grid: GridDef,
) -> np.ndarray:
    rows, cols = rowcol(grid.transform, lons, lats)
 
    valid = (
        (rows >= 0) & (rows < grid.height) &
        (cols >= 0) & (cols < grid.width)
    )
    rows, cols = rows[valid], cols[valid]
 
    flat = rows * grid.width + cols
    counts = np.bincount(
        flat, minlength=grid.height * grid.width,
    ).reshape(grid.height, grid.width).astype(np.float32)
 
    log.info(
        "GNAF grid: %d populated pixels, max count=%d, mean=%.2f",
        (counts > 0).sum(), counts.max(), counts[counts > 0].mean(),
    )
    return counts

# Mesh Block fallback weights: SA2s with zero GNAF coverage
def _build_mesh_block_fallback(
    gdf: gpd.GeoDataFrame,
    grid: GridDef,
) -> np.ndarray:
    populated = gdf[gdf["MB_CATEGORY_2021"].isin(FALLBACK_WEIGHTS)].copy()
    populated["weight"] = populated["MB_CATEGORY_2021"].map(FALLBACK_WEIGHTS)
 
    fallback = np.zeros((grid.height, grid.width), dtype=np.float32)
    shapes = (
        (geom, float(w))
        for geom, w in zip(populated.geometry, populated["weight"])
        if geom is not None
    )
    rio_features.rasterize(
        shapes=shapes,
        out=fallback,
        transform=grid.transform,
        fill=0.0,
        all_touched=True,
        dtype=np.float32,
    )
    return fallback

# Get SA2 boundaries as raster lookup
def _build_sa2_id_raster(
    gpkg_path: Path,
    grid: GridDef
) -> tuple[np.ndarray, dict[int, str]]:
    sa2_gdf = gpd.read_file(
        gpkg_path,
        layer="SA2_2021_AUST_GDA2020",
        columns=["SA2_CODE_2021", "geometry"],
    ).to_crs(epsg=7844)
 
    sa2_gdf["id"] = np.arange(1, len(sa2_gdf) + 1, dtype=np.int32)
    id_to_code = dict(zip(sa2_gdf["id"], sa2_gdf["SA2_CODE_2021"]))
 
    sa2_ids = np.zeros((grid.height, grid.width), dtype=np.int32)   # Raster map of sa2 ids
    shapes = (
        (geom, int(i))
        for geom, i in zip(sa2_gdf.geometry, sa2_gdf["id"])
        if geom is not None
    )
    rio_features.rasterize(
        shapes=shapes,
        out=sa2_ids,
        transform=grid.transform,
        fill=0,
        dtype=np.int32,
    )
    return sa2_ids, id_to_code


# Build weighted mask
# Per pixel weights for a single SA2 should sum to 1
def build_weighted_mask(
    gpkg_path: Path = GPKG_PATH,
    gnaf_path: Path = GNAF_PATH,
    grid: GridDef = NATIONAL_GRID,
    force: bool = False
) -> np.ndarray:
    out_path = OUTPUT_DIR/"sa2_weighted_mask.tif"
    if out_path.exists() and not force:
        log.info("Loading cached mask")
        with rasterio.open(out_path) as src:
            return src.read(1)
 
    # Loading inputs
    mb_gdf = _load_mesh_blocks(gpkg_path)
    b_mask = build_binary_mask(gpkg_path, grid, force=force)
    sa2_ids, _ = _build_sa2_id_raster(gpkg_path, grid)
    mb_fallback = _build_mesh_block_fallback(mb_gdf, grid)
    lons, lats   = _load_gnaf(gnaf_path)
    gnaf_counts  = _bin_gnaf(lons, lats, grid)

    # Binary exclusion mask on GNAF, MB_Fallback
    bool_mask = b_mask.astype(bool)
    gnaf_counts[bool_mask] = 0.0
    mb_fallback[bool_mask] = 0.0

    # Flattened vectors for faster operations
    flat_ids = sa2_ids.ravel()
    flat_gnaf = gnaf_counts.ravel()
    flat_mb = mb_fallback.ravel()

    # Total GNAF addresses for each SA2 id
    n = sa2_ids.max() + 1
    sa2_gnaf_totals = np.bincount(flat_ids, weights=flat_gnaf, minlength=n)
 
    # SA2 with GNAF coverage
    pixel_sa2_gnaf_total = sa2_gnaf_totals[flat_ids] # Spread totals over the full vector
    gnaf_covered = pixel_sa2_gnaf_total > 0

    # Mesh block fallbacks
    sa2_mb_totals = np.bincount(flat_ids, weights=flat_mb, minlength=n)
    pixel_sa2_mb_total = sa2_mb_totals[flat_ids]

    # Calculate fractional weights: 
    # To ensure population numbers remain unchanged, all fractions for a single SA2 sum to 1
    # This is achieved by dividing each raw score by the total sum of SA2
    flat_fractions = np.where(
        gnaf_covered,
        np.where(pixel_sa2_gnaf_total > 0, flat_gnaf / pixel_sa2_gnaf_total, 0.0), # GNAF
        np.where(pixel_sa2_mb_total > 0, flat_mb  / pixel_sa2_mb_total, 0.0), # MB fallback
    ).astype(np.float32)

    fractions = flat_fractions.reshape(grid.height, grid.width) # Back into raster



    # --- Diagnostics ---
    n_sa2s_total    = len(np.unique(flat_ids[flat_ids > 0]))
    n_sa2s_gnaf     = int((sa2_gnaf_totals[1:] > 0).sum())
    n_sa2s_fallback = n_sa2s_total - n_sa2s_gnaf
    log.info(
        "SA2 coverage: %d total | %d GNAF (%.1f%%) | %d MB fallback (%.1f%%)",
        n_sa2s_total,
        n_sa2s_gnaf,     100 * n_sa2s_gnaf     / n_sa2s_total,
        n_sa2s_fallback, 100 * n_sa2s_fallback / n_sa2s_total,
    )
 
    # Sanity: spot-check that fractions within a sample SA2 sum to ~1.0
    sample_ids = np.unique(flat_ids[flat_ids > 0])
    if len(sample_ids):
        sid        = sample_ids[len(sample_ids) // 2]
        sample_sum = fractions[sa2_ids == sid].sum()
        log.info("Sample SA2 fraction sum: %.6f (should be 1.0)", sample_sum)
 


    write_cog(fractions, out_path, grid=grid, nodata=None, band_name="sa2_weight_fraction")
    log.info("Weight fractions written → %s", out_path)
    return fractions



if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
 
    force = "--force" in sys.argv
 
    excl = build_binary_mask(force=force)
    fracs = build_weighted_mask(force=force)
 
    print(f"\nExclusion mask:   {excl.sum():,} pixels excluded"
          f" ({100*excl.sum()/excl.size:.1f}%)")
    print(f"Weight fractions: min={fracs[fracs>0].min():.6f}"
          f"  max={fracs.max():.6f}")
    print(f"                  non-zero pixels: {(fracs>0).sum():,}")