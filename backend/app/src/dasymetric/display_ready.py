# Helper: deprecated

import logging
from pathlib import Path
 
import numpy as np
import rasterio

OUTPUT_DIR = Path("data/outputs/rasters/dasymetric")

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("Error: provide target year.")
        sys.exit(0)
    year = sys.argv[1]

    with rasterio.open(f"{OUTPUT_DIR}/erp_weighted_20{year}.tif") as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile

    data[data <= 0] = np.nan
    log_data = np.log1p(data)

    # Stretch to 0–255 uint8 for preview
    p2, p98 = np.nanpercentile(log_data, 2), np.nanpercentile(log_data, 98)
    display = np.clip((log_data - p2) / (p98 - p2) * 255, 0, 255)
    display = np.nan_to_num(display, nan=0).astype(np.uint8)

    profile.update(dtype="uint8", nodata=0)
    with rasterio.open(f"{OUTPUT_DIR}/erp_weighted_20{year}_preview.tif", "w", **profile) as dst:
        dst.write(display, 1)