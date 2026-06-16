from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from titiler.core.factory import TilerFactory
from titiler.core.dependencies import create_colormap_dependency
from rio_tiler.colormap import cmap
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from pathlib import Path
from fastapi.responses import Response
from rio_tiler.io import COGReader
import numpy as np
import rasterio
from rasterio.transform import rowcol
from contextlib import asynccontextmanager

from .src.index.colour_ramp import register_colourmaps
from .src.dasymetric.ancillary_mask import _build_sa2_id_raster

from app.routers import health

LOG_SCALE_INDICATORS = {"erp", "housing_price"}
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "outputs"

SA2_ID_RASTER: np.ndarray | None = None
SA2_ID_TO_CODE: dict[int, str] = {}
SA2_ID_TRANSFORM = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global SA2_ID_RASTER, SA2_ID_TO_CODE, SA2_ID_TRANSFORM
    SA2_ID_RASTER, SA2_ID_TO_CODE, SA2_ID_TRANSFORM = _build_sa2_id_raster()
    print(f"Serving data from: {DATA_DIR.resolve()}")
    yield

updated_cmap = register_colourmaps()
ColorMapParams = create_colormap_dependency(updated_cmap)

cog = TilerFactory(colormap_dependency=ColorMapParams)

app = FastAPI(
    title="Purview Dashboard API",
    description="REST API for the Purview Dashboard",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://frontend:80",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cog.router, prefix="/api/cog")
add_exception_handlers(app, DEFAULT_STATUS_CODES)

app.include_router(health.router, prefix="/api")

# HELPERS
def _resolve_cog_path(indicator: str, year: str) -> Path:
    cog_path = DATA_DIR / "rasters" / "dasymetric" / f"{indicator}_weighted_{year}.tif"
    if not cog_path.exists():
        raise HTTPException(status_code=404, detail=f"No raster for {indicator} {year}")
    return cog_path

def _rescale_range(indicator: str, b1) -> tuple[float, float]:
    raw_max = float(b1.percentile_98) or float(b1.max)
    if indicator in LOG_SCALE_INDICATORS:
        return 0.0, float(np.log1p(raw_max))
    return 0.0, raw_max

def _lookup_sa2(lat: float, lon: float) -> dict:
    if SA2_ID_RASTER is None:
        return {"sa2_code": None, "sa2_name": None}
    row, col = rowcol(SA2_ID_TRANSFORM, lon, lat)
    if not (0 <= row < SA2_ID_RASTER.shape[0] and 0 <= col < SA2_ID_RASTER.shape[1]):
        return {"sa2_code": None, "sa2_name": None}
    sa2_id = SA2_ID_RASTER[row, col]
    if sa2_id == 0:
        return {"sa2_code": None, "sa2_name": None}
    return {"sa2_code": SA2_ID_TO_CODE.get(int(sa2_id)), "sa2_name": None}

# ENDPOINTS
'''
@app.middleware("http")
async def add_aggressive_tile_caching(request: Request, call_next):
    response = await call_next(request)
    if ("/tiles" in request.url.path or "/preview" in request.url.path) and (response.status_code == 200):
        response.headers["Cache-Control"] = "public, max-age=86400, immutable" # 1 day cache
    return response
'''
@app.get("/api/cog/datasets/{indicator}/{year}")
async def cog_dataset(indicator: str, year: str) -> dict:
    cog_path = _resolve_cog_path(indicator, year)
    with COGReader(str(cog_path)) as cog:
        stats = cog.statistics()
        b1    = stats["b1"]
        r_min, r_max = _rescale_range(indicator, b1)
        return {
            "path":    str(cog_path.resolve()),
            "minzoom": cog.minzoom,
            "maxzoom": cog.maxzoom,
            "rescale": [r_min, r_max],
        }

@app.get("/api/tiles/{indicator}/{year}/{z}/{x}/{y}")
async def get_tile(
    indicator: str,
    year: str,
    z: int,
    x: int,
    y: int,
    rescale: str | None = None,
) -> Response:
    cog_path = _resolve_cog_path(indicator, year)
    try:
        with COGReader(str(cog_path)) as cog:
            if not cog.tile_exists(x, y, z):
                raise HTTPException(status_code=404, detail="Tile outside bounds")

            img = cog.tile(x, y, z, indexes=[1])

            if indicator in LOG_SCALE_INDICATORS:
                nodata_pixels = img.data[0] < 0
                valid = ~nodata_pixels
                safe_data = np.clip(img.data[0], 0.0, None)
                img.data[0] = np.where(valid, np.log1p(safe_data), 0.0)
                img.mask[:] = np.where(valid, 255, 0).astype(np.uint8)
            if rescale:
                r_min, r_max = (float(v) for v in rescale.split(","))
            else:
                stats = cog.statistics()
                r_min, r_max = _rescale_range(indicator, stats["b1"])
            img.rescale(in_range=((r_min, r_max),))

            cm = updated_cmap.get(indicator)
            content = img.render(img_format="PNG", colormap=cm)
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(content, media_type="image/png")

@app.get("/api/stats")
async def get_pixel_stats(lat: float, lon: float, year: str) -> dict:
    indicators = ["erp", "unemployment_rate", "seifa", "housing_price", "liveability"]
    result: dict = {"lat": lat, "lon": lon, "sa2_code": None, "sa2_name": None}

    for indicator in indicators:
        cog_path = DATA_DIR / "rasters" / "dasymetric" / f"{indicator}_weighted_{year}.tif"
        if not cog_path.exists():
            result[indicator] = None
            continue

        with rasterio.open(cog_path) as src:
            row, col = rowcol(src.transform, lon, lat)
            if 0 <= row < src.height and 0 <= col < src.width:
                value = src.read(1, window=((row, row+1), (col, col+1)))[0, 0]
                result[indicator] = None if value <= -9000.0 else float(value)
            else:
                result[indicator] = None

    # SA2 lookup — needs the SA2 boundary GeoPackage, point-in-polygon
    sa2_info = _lookup_sa2(lat, lon)
    result.update(sa2_info)

    return result

app.mount(
    "/data",
    StaticFiles(directory=str(DATA_DIR)),
    name="data",
)

print(f"Serving data from: {DATA_DIR.resolve()}")

@app.get("/")
def root():
    return {"message": "Purview Dashboard API", "docs": "/docs"}
