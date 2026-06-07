"""
write_cog.py
Converts an existing GeoTIFF to a proper Cloud-Optimised GeoTIFF.
 
Usage:
    python write_cog.py <input.tif>
    python write_cog.py <input.tif> <output.tif>
 
If no output path is given, overwrites the input file.
 
A proper COG requires:
    - Internal tiling (256x256)
    - Overviews built BEFORE the final write
    - COPY_SRC_OVERVIEWS=YES via gdal_translate
    - LZW compression -> switch to 'deflate' ?
    - Numeric nodata value (not NaN) for correct masking in titiler
"""
 
import logging
import shutil
import subprocess
import sys
from pathlib import Path
 
import numpy as np
import rasterio
from rasterio.enums import Resampling
 
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)
 
OVERVIEW_LEVELS = [2, 4, 8, 16, 32, 64, 128]
TILE_SIZE       = 512
COMPRESS        = "deflate"
NODATA          = -9999.0   # numeric nodata — NaN causes masking issues in titiler
 
 
def convert_to_cog(src_path: Path, dst_path: Path | None = None) -> Path:
    src_path  = Path(src_path)
    overwrite = dst_path is None
    dst_path  = Path(dst_path) if dst_path else src_path
    tmp_path  = src_path.with_suffix(".ovr_tmp.tif")
 
    if not src_path.exists():
        raise FileNotFoundError(f"Input file not found: {src_path}")
 
    log.info("Source:      %s", src_path)
    log.info("Destination: %s", dst_path)
 
    # --- Step 1: copy to temp, replacing NaN nodata with numeric value ---
    log.info("Copying to temp file (replacing NaN nodata with %s)…", NODATA)
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        src_nodata = src.nodata
 
        profile.update(nodata=NODATA)
 
        with rasterio.open(tmp_path, "w", **profile) as dst:
            for band_idx in src.indexes:
                data = src.read(band_idx)
 
                # Replace NaN with numeric nodata
                if src_nodata is not None and np.isnan(src_nodata):
                    data = np.where(np.isnan(data), NODATA, data)
                elif src_nodata is not None:
                    data = np.where(data == src_nodata, NODATA, data)
 
                dst.write(data, band_idx)
 
    try:
        # --- Step 2: build overviews on temp file ---
        log.info("Building overviews %s…", OVERVIEW_LEVELS)
        with rasterio.open(tmp_path, "r+") as tmp:
            tmp.build_overviews(OVERVIEW_LEVELS, Resampling.average)
            tmp.update_tags(ns="rio_overview", resampling="average")
            log.info("Overviews built: %s", tmp.overviews(1))
 
        # --- Step 3: write COG via gdal_translate ---
        log.info("Writing COG via gdal_translate…")
        write_target = (
            dst_path.with_suffix(".cog_tmp.tif") if overwrite else dst_path
        )
        write_target.parent.mkdir(parents=True, exist_ok=True)
 
        result = subprocess.run([
            "gdal_translate",
            "-of",  "GTiff",
            "-co",  "COMPRESS=DEFLATE",
            "-co",  "PREDICTOR=2",
            "-co",  "TILED=YES",
            "-co",  f"BLOCKXSIZE={TILE_SIZE}",
            "-co",  f"BLOCKYSIZE={TILE_SIZE}",
            "-co",  "COPY_SRC_OVERVIEWS=YES",
            "-a_nodata", str(NODATA),
            str(tmp_path),
            str(write_target),
        ], capture_output=True, text=True)
 
        if result.returncode != 0:
            raise RuntimeError(f"gdal_translate failed:\n{result.stderr}")
 
        if overwrite:
            write_target.replace(dst_path)
 
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
 
    # --- Verify ---
    log.info("Verifying output…")
    with rasterio.open(dst_path) as out:
        data = out.read(1)
        valid = data != NODATA
        log.info("  CRS:          %s", out.crs)
        log.info("  Bounds:       %s", out.bounds)
        log.info("  Shape:        %d x %d", out.height, out.width)
        log.info("  Overviews:    %s", out.overviews(1))
        log.info("  Nodata:       %s", out.nodata)
        log.info("  Valid pixels: %d / %d (%.1f%%)",
                 valid.sum(), data.size, 100 * valid.sum() / data.size)
        log.info("  Value range:  %.4f → %.4f",
                 data[valid].min() if valid.any() else 0,
                 data[valid].max() if valid.any() else 0)
        log.info("  Size:         %.1f MB", dst_path.stat().st_size / 1e6)
 
    log.info("Done → %s", dst_path)
    return dst_path
 
 
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python write_cog.py <input.tif> [output.tif]")
        sys.exit(1)
 
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else None
 
    convert_to_cog(src, dst)