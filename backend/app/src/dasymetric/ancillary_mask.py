'''
    2-Stage masking for population-related data
    
    1. Binary mask: exclusion with mesh block categories and data
    2. Weighted mask: based on GNAF address density (with mesh block fallback)
'''

import logging
from pathlib import Path
 
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

MB_FALLBACK_WEIGHTS: dict[str, float] = {
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
    )
    if gdf.crs.to_epsg() != 7844:
        gdf = gdf.to_crs(epsg=7844)
    
    unknown = set(gdf["MB_CATEGORY_2021"].unique()) - MB_EXCLUDED - set(MB_FALLBACK_WEIGHTS)
    if unknown: log.warning("Unknown MB categories excluded: %s", unknown)
    return gdf

def _build_exclusion_mask(
    gpkg_path: Path = GPKG_PATH,
    grid: GridDef = NATIONAL_GRID,
    force: bool = False,
) -> np.ndarray:
    out_path = OUTPUT_DIR / "exclusion_mask.tif"
    if out_path.exists() and not force:
        log.info("Loading cached exclusion mask")
        with rasterio.open(out_path) as src:
            return src.read(1)
 
    gdf = _load_mb_layer(gpkg_path)
 
    # Only burn excluded categories — value 1 means excluded
    excluded_gdf = gdf[gdf["MB_CATEGORY_2021"].isin(MB_EXCLUDED)]
    log.info(
        "Exclusion MBs: %d / %d mesh blocks",
        len(excluded_gdf), len(gdf),
    )
 
    mask = np.zeros((grid.height, grid.width), dtype=np.uint8)
    shapes = (
        (geom, 1)
        for geom in excluded_gdf.geometry
        if geom is not None
    )
    rio_features.rasterize(
        shapes=shapes,
        out=mask,
        transform=grid.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )
 
    pct = 100 * mask.sum() / mask.size
    log.info("Excluded pixels: %d / %d (%.1f%%)", mask.sum(), mask.size, pct)
    write_cog(mask.astype(np.float32), out_path, grid=grid, nodata=None,
              band_name="exclusion_mask")
    return mask