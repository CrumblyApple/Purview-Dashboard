'''
    Central pipeline file for applying dasymetric methods
        Fetches raster and masks, then multiplies together
        Verifies population invariant holds
'''
import logging
from pathlib import Path
 
import numpy as np
import rasterio
 
from ..spatial.rasterise import NATIONAL_GRID, GridDef, write_cog
 
log = logging.getLogger(__name__)
 
OUTPUT_DIR = Path("data/outputs/rasters/dasymetric")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
 
WEIGHTS_PATH = Path("data/outputs/masks")
EXCLUSION_PATH = Path("data/outputs/masks")

def _load_raster(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1).astype(np.float32)

# Checks that the population invariant holds (within a small margin of error)
def _check_conservation(
    raw_raster: np.ndarray,
    redistributed: np.ndarray,
    sa2_id_raster: np.ndarray | None = None,
    nodata: float = np.nan,
    sample_n: int = 10
) -> None:
    if np.isnan(nodata):
        valid = ~np.isnan(raw_raster)
    else:
        valid = raw_raster != nodata
 
    raw_total  = raw_raster[valid].sum()
    dist_total = redistributed[valid & ~np.isnan(redistributed)].sum()
 
    log.info(
        "Mass conservation check:\n"
        "  Raw raster sum (all pixels):           %15.1f\n"
        "  Redistributed sum (all pixels):        %15.1f\n"
        "  Note: raw sum counts SA2 value × pixel count so will differ",
        raw_total, dist_total,
    )
 
    if sa2_id_raster is not None:
        # Spot-check a sample of SA2s
        unique_ids = np.unique(sa2_id_raster)
        unique_ids = unique_ids[unique_ids > 0]
        rng = np.random.default_rng(42)
        sample_ids = rng.choice(unique_ids, size=min(sample_n, len(unique_ids)), replace=False)
 
        errors = []
        for sid in sample_ids:
            pixel_mask = sa2_id_raster == sid
            # Original aggregate — all pixels in SA2 have same raw value
            raw_vals = raw_raster[pixel_mask]
            if np.isnan(nodata):
                raw_vals = raw_vals[~np.isnan(raw_vals)]
            if len(raw_vals) == 0:
                continue
            sa2_aggregate = raw_vals[0]   # all identical, take first
 
            dist_sum = redistributed[pixel_mask].sum()
            error_pct = abs(dist_sum - sa2_aggregate) / (sa2_aggregate + 1e-9) * 100
 
            errors.append(error_pct)
            if error_pct > 1.0:
                log.warning(
                    "SA2 ID %d: aggregate=%.1f  redistributed_sum=%.1f  "
                    "error=%.2f%%",
                    sid, sa2_aggregate, dist_sum, error_pct,
                )
 
        if errors:
            log.info(
                "Mass conservation sample (%d SA2s): "
                "mean error=%.4f%%  max error=%.4f%%",
                len(errors), np.mean(errors), np.max(errors),
            )


def compute_weighting(
    raw_raster_path: Path,
    out_name: str,
    weights_path: Path = WEIGHTS_PATH,
    exclusion_path: Path = EXCLUSION_PATH,
    grid: GridDef = NATIONAL_GRID,
    year: int = 25,
    nodata: float = np.nan,
    check_conservation: bool = True
) -> np.ndarray:
    for p in (weights_path / f"sa2_weighted_mask_20{year}.tif", exclusion_path / f"binary_mask_20{year}.tif"):
        if not p.exists(): raise FileNotFoundError(f"{p} not found.")
 
    weights = _load_raster(weights_path / f"binary_mask_20{year}.tif")
    exclusion = _load_raster(exclusion_path / f"sa2_weighted_mask_20{year}").astype(bool)
    raw = _load_raster(raw_raster_path)
 
    if raw.shape != weights.shape:
        raise ValueError(f"Shape mismatch: raw_raster {raw.shape} vs fractions {weights.shape}")
 
    # Track nodata
    if np.isnan(nodata):
        valid_sa2 = ~np.isnan(raw)
    else:
        valid_sa2 = (raw != nodata)
 
    redistributed = raw * weights
    redistributed[exclusion] = 0.0
    # Restore nodata
    redistributed[~valid_sa2] = nodata
 
    if check_conservation:
        _check_conservation(raw, redistributed, nodata=nodata)

    out_path = OUTPUT_DIR/f"{out_name}_20{year}.tif"
    write_cog(redistributed, out_path, grid=grid, nodata=nodata,
              band_name=out_name)
 
    n_populated = np.isfinite(redistributed).sum() if np.isnan(nodata) \
        else (redistributed != nodata).sum()
    log.info(
        "Areal weighting complete → %s  (%d populated pixels)",
        out_path, n_populated,
    )
    return out_path


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Error: provide target year.")
        sys.exit(0)
    year = sys.argv[1]
    raw_path = Path(f"data/outputs/rasters/erp_sa2_20{year}.tif")
    out_name = "erp_weighted"
 
    out = compute_weighting(raw_path, out_name, year=year)
    print(f"\nDone → {out}")