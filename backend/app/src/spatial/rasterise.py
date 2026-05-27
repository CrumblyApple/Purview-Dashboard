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
    "left":   112.9,   # west
    "right":  153.7,   # east
    "top":    -9.9,    # north
    "bottom": -43.7,   # south
}
 
RESOLUTION = 0.0025   # degrees, ~250m at Australian latitudes
CRS_EPSG   = 7844     # GDA2020 geographic

@dataclass(frozen=True)
class GridDef:
    left:       float
    right:      float
    top:        float
    bottom:     float
    resolution: float
    epsg:       int
 
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
    **AUSTRALIA_BOUNDS,
)



