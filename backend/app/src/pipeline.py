import sys
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .ingest.abs_ingest import ABSClient, DATASETS
from .ingest.gnaf_ingest import convert
from .spatial.rasterise import rasterise_stat
from .spatial import gpkg_join as joiner
from .spatial.write_cog import convert_to_cog
from .dasymetric.ancillary_mask import build_weighted_mask, GNAF_PATH
from .dasymetric.areal_weighting import compute_weighting
 
log = logging.getLogger(__name__)

YEARS = [21, 22, 23, 24, 25]

def pipeline(years: list[int] = YEARS, force: bool = False):

    with ABSClient() as client:
        erp = client.fetch("erp_sa2", force=force)

    erp = erp[["ASGS_2021", "TIME_PERIOD", "value"]]
 
    log.info("ERP years available: %s", sorted(erp["TIME_PERIOD"].unique()))

    for year in years:
        log.info("Working on year: %s", f"20{year}")
        if not Path(GNAF_PATH / f"gnaf_core_20{year}.parquet").is_file():
            log.info("Building GNAF")
            convert(year)

        erp_year = erp[erp["TIME_PERIOD"] == f"20{year}"].copy()
        gdf = joiner.join_cross_section(
            erp_year,
            "erp",
            value_col="value"
        )

        log.info("Rasterising") 
        out_path = rasterise_stat(
            gdf,
            target_col="value",
            out_name=f"erp_sa2_20{year}",
        )

        log.info("Building masks")
        build_weighted_mask(year=year, force=force)

        out_name = "erp_weighted"

        log.info("Computing weights")
        out = compute_weighting(out_path, out_name, year=year)

        log.info("Finalising...")
        convert_to_cog(out)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    force = "--force" in sys.argv

    pipeline(force=force)