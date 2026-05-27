'''
    Joins ingested ABS dataframe with ASGS boundary polygons (from geopackage)
'''
 
import logging
from pathlib import Path
from typing import Any
 
import fiona
import geopandas as gpd
import pandas as pd
 
log = logging.getLogger(__name__)

GPKG_PATH = Path("data/raw/asgs_3/ASGS_2021_Main_Structure_GDA2020.gpkg")

# TODO: migrate out
STAT_CONFIG: dict[str, dict] = {
    "erp": {
        "geography":   "sa2",
        "df_code_col": "ASGS_2021",
    },
}

# Potential naming schemes (ABS can be inconsistent)
# TODO: Geocodes as ENUMS?
GEOGRAPHY_META: dict[str, dict] = {
    "sa2": {
        "layer_patterns": ["SA2_2021", "SA2_2021_AUST"],
        "code_patterns":  ["SA2_CODE_2021", "SA2_CODE21", "SA2_MAINCODE_2021"],
    },
}

# Layer name coercion
def _determine_layer(geography: str, gpkg_path: Path) -> str:
    layers = fiona.listlayers(str(gpkg_path))
    patterns  = GEOGRAPHY_META[geography]["layer_patterns"]
 
    for layer in layers:
        for pattern in patterns:
            if pattern.upper() in layer.upper():
                return layer
 
    raise ValueError(
        f"Could not find a '{geography.upper()}' layer in {gpkg_path}.\n"
        f"Available layers: {layers}\n"
        f"Expected one matching: {patterns}"
    )

# Code column name coercion
def _determine_code_column(gdf: gpd.GeoDataFrame, geography: str) -> str:
    patterns = GEOGRAPHY_META[geography]["code_patterns"]
 
    for col in gdf.columns:
        for pattern in patterns:
            if col.upper() == pattern.upper():
                return col
 
    raise ValueError(
        f"Could not find a {geography.upper()} code column.\n"
        f"Columns present: {list(gdf.columns)}\n"
        f"Expected one of: {patterns}"
    )


# Load boundary polygons from GeoPackage    [GDA2020]
_boundary_cache: dict[str, gpd.GeoDataFrame] = {}

def load_boundaries(
    geography: str,                         # ie 'sa2'
    gpkg_path: Path = GPKG_PATH,
    columns: list[str] | None = None,       # Column filter
) -> gpd.GeoDataFrame:
    cache_key = f"{gpkg_path}:{geography}"
    if cache_key in _boundary_cache:
        log.debug("Boundary cache hit for '%s'", geography)
        return _boundary_cache[cache_key]
 
    if not gpkg_path.exists():
        raise FileNotFoundError(f"GeoPackage not found at {gpkg_path}.")
 
    layer = _determine_layer(geography, gpkg_path)
    log.info("Loading boundaries: layer '%s' from %s", layer, gpkg_path.name)
 
    gdf = gpd.read_file(gpkg_path, layer=layer, columns=columns)
 
    # Ensure GDA2020 coordinate system
    if gdf.crs is None:
        log.warning("Boundary layer has no CRS | Defaulting to EPSG:7844 (GDA2020)")
        gdf = gdf.set_crs(epsg=7844)
    elif gdf.crs.to_epsg() != 7844:
        log.info("Reprojecting boundaries from EPSG:%s to EPSG:7844", gdf.crs.to_epsg())
        gdf = gdf.to_crs(epsg=7844)
 
    _boundary_cache[cache_key] = gdf
    log.info("Loaded %d polygons, columns: %s", len(gdf), list(gdf.columns))
    return gdf


# Joins a given abs dataset to the geopackage boundaries
# MUST BE A SINGLE CROSS-SECTION : NO TIME SERIES
# Data is NaN when there is a boundary polygon with no associated data
def join_cross_section(
    df: pd.Dataframe,
    stat: str,          # TODO: make ENUM
    value_col: str,     # Column containing actual data that we want to keep
    gpkg_path: Path = GPKG_PATH,
    drop_unused: bool = True
) -> gpd.GeoDataFrame:
    if stat not in STAT_CONFIG:
        raise ValueError(f"Unknown statistic '{stat}'")

    geography = STAT_CONFIG[stat]["geography"]
    df_code_col = STAT_CONFIG[stat]["df_code_col"]

    # The ABS ingest data we want to keep
    if df_code_col not in df.columns:
        raise KeyError(f"Expected code column '{df_code_col}' not found in DataFrame")
    if value_col not in df.columns:
        raise KeyError(f"Expected value column '{value_col}' not found in DataFrame")

    boundaries = load_boundaries(geography, gpkg_path).copy()   # Leave cache intact
    boundary_code_col = _determine_code_column(boundaries, geography)

    # Convert column names to strings
    boundaries[boundary_code_col] = (boundaries[boundary_code_col].astype(str).str.strip())
    df[df_code_col] = df[df_code_col].astype(str).str.strip()

    # Drop irrelavant data
    slim_df = df[[df_code_col, value_col]].copy()

    merged = boundaries.merge(
        slim_df,
        left_on=boundary_code_col,
        right_on=df_code_col,
        how='left',
    )
    # We only need one instance of the geography codes
    if df_code_col != boundary_code_col and df_code_col in merged.columns:
        merged = merged.drop(columns=[df_code_col])

    if drop_unused:
        keep = {boundary_code_col, value_col, "geometry"}
        drop_cols = [c for c in merged.columns if c not in keep]
        if drop_cols:
            merged = merged.drop(columns=drop_cols)
    return merged


# Inspector
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
 
    gpkg = Path(sys.argv[1]) if len(sys.argv) > 1 else GPKG_PATH
 
    if not gpkg.exists():
        print(f"GeoPackage not found: {gpkg}")
        sys.exit(1)
 
    print(f"\nGeoPackage: {gpkg}")
    print(f"Layers found:")
    for layer in fiona.listlayers(str(gpkg)):
        gdf = gpd.read_file(gpkg, layer=layer, rows=1)
        print(f"  {layer}")
        print(f"    CRS:     {gdf.crs}")
        print(f"    Columns: {list(gdf.columns)}\n")