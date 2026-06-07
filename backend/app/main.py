from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from titiler.core.factory import TilerFactory
from titiler.core.dependencies import create_colormap_dependency
from rio_tiler.colormap import cmap
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from pathlib import Path
from fastapi.responses import Response
from rio_tiler.io import COGReader

from .src.index.colour_ramp import register_colourmaps

from app.routers import health

updated_cmap = register_colourmaps()

ColorMapParams = create_colormap_dependency(updated_cmap)

cog = TilerFactory(
    colormap_dependency=ColorMapParams,
)

is_registered = "erp" in updated_cmap.list()

print(f"--- COLORMAP CHECK ---")
print(f"Is 'erp' registered globally? {is_registered}")
print(f"Available custom/total maps: {len(updated_cmap.list())}")
print(f"----------------------")

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

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "outputs"


def _resolve_cog_path(indicator: str, year: str) -> Path:
    cog_path = DATA_DIR / "rasters" / "dasymetric" / f"{indicator}_weighted_{year}.tif"
    if not cog_path.exists():
        raise HTTPException(status_code=404, detail=f"No raster for {indicator} {year}")
    return cog_path


@app.get("/api/cog/datasets/{indicator}/{year}")
async def cog_dataset(indicator: str, year: str):
    """Return local COG path and metadata for titiler tile requests."""
    cog_path = _resolve_cog_path(indicator, year)
    with COGReader(str(cog_path)) as reader:
        stats = reader.statistics()
        b1 = stats.get("b1")
        vmax = b1.max if b1 is not None else 100
        return {
            "path": str(cog_path.resolve()),
            "minzoom": reader.minzoom,
            "maxzoom": reader.maxzoom,
            "rescale": [0, vmax],
        }


@app.get("/api/tiles/{indicator}/{year}/{z}/{x}/{y}")
async def get_tile(indicator: str, year: str, z: int, x: int, y: int):
    """Resolve COG path locally and proxy to titiler internals."""
    from titiler.core.algorithm import algorithms
    from rio_tiler.io import COGReader

    cog_path = _resolve_cog_path(indicator, year)

    with COGReader(str(cog_path)) as cog:
        img = cog.tile(x, y, z)
        content = img.render(img_format="PNG")

    return Response(content, media_type="image/png")

@app.get("/api/raster/info/{indicator}/{year}")
async def raster_info(indicator: str, year: str):
    cog_path = _resolve_cog_path(indicator, year)
    with COGReader(str(cog_path)) as cog:
        return {
            "bounds":      cog.bounds,
            "minzoom":     cog.minzoom,
            "maxzoom":     cog.maxzoom,
            "statistics":  cog.statistics(),
        }

app.mount(
    "/data",
    StaticFiles(directory=str(DATA_DIR)),
    name="data",
)

print(f"Serving data from: {DATA_DIR.resolve()}")


@app.get("/")
def root():
    return {"message": "Purview Dashboard API", "docs": "/docs"}
