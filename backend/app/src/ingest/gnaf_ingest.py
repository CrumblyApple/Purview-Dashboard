'''
    Converts a GNAF file into a parquet
'''
import sys
import logging
import zipfile
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Point this at wherever you extracted the GNAF zip
GNAF_RAW_DIR = Path("data/raw/gnaf/raw")
GNAF_OUT     = Path("data/raw/gnaf/")

STATES = ["ACT", "NSW", "NT", "OT", "QLD", "SA", "TAS", "VIC", "WA"]
EXCLUDED_CODES = ["STL", "LOC"]
KEEP_COLS = ["ADDRESS_DETAIL_PID", "LATITUDE", "LONGITUDE", "GEOCODE_TYPE_CODE", "CONFIDENCE"]

def convert(year: int, raw_dir: Path = GNAF_RAW_DIR) -> pd.DataFrame:
    zips = list(raw_dir.rglob(f"g-naf_*{year}_*.zip"))
    if not zips: raise FileNotFoundError(f"No zip file found under {raw_dir}.")
    zip_path = zips[0]
    log.info("Reading GNAF from %s", zip_path.name)

    frames = []
    with zipfile.ZipFile(zip_path) as zf:
        all_names = zf.namelist()

        for state in STATES:
            detail_name  = next((n for n in all_names if f"{state}_ADDRESS_DETAIL_psv" in n), None)
            geocode_name = next((n for n in all_names if f"{state}_ADDRESS_DEFAULT_GEOCODE_psv" in n), None)

            if not detail_name or not geocode_name:
                log.warning("Skipping %s: PSV files not found", state)
                continue

            with zf.open(detail_name) as f:
                detail = pd.read_csv(f, sep="|", dtype=str, low_memory=False)

            with zf.open(geocode_name) as f:
                geocode = pd.read_csv(f, sep="|", dtype=str, low_memory=False)

            merged = detail.merge(
                geocode[["ADDRESS_DETAIL_PID", "LATITUDE", "LONGITUDE", "GEOCODE_TYPE_CODE"]],
                on="ADDRESS_DETAIL_PID",
                how="inner",
            )

            merged = merged[
                (merged["ALIAS_PRINCIPAL"] == "P") & 
                ~merged["GEOCODE_TYPE_CODE"].isin(EXCLUDED_CODES) &
                (merged["CONFIDENCE"].astype(int) >= 0)
            ][KEEP_COLS].copy()
            merged["LATITUDE"]  = pd.to_numeric(merged["LATITUDE"],  errors="coerce")
            merged["LONGITUDE"] = pd.to_numeric(merged["LONGITUDE"], errors="coerce")
            merged = merged.dropna(subset=["LATITUDE", "LONGITUDE"])

            frames.append(merged)
            log.info("%-3s  %d addresses", state, len(merged))

    df = pd.concat(frames, ignore_index=True)
    log.info("Total: %d addresses → %s", len(df), GNAF_OUT)

    GNAF_OUT.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(GNAF_OUT / f"gnaf_core_20{year}.parquet", index=False)
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    
    if len(sys.argv) < 2:
        print("Error: provide target year.")
        sys.exit(0)

    convert(sys.argv[1], GNAF_RAW_DIR)
