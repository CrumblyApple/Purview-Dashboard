'''
This module is used to ingest data from the ABS API.
ABS DataAPI base: https://data.api.abs.gov.au/rest
API Documentation: https://www.abs.gov.au/about/data-services/application-programming-interfaces-apis/data-api-user-guide

SA2 SDMX-JSON | Datasets:
- Estimated Resident Population: https://data.api.abs.gov.au/rest/data/ABS_ANNUAL_ERP_ASGS2021/ERP.SA2..A?startPeriod=2025&endPeriod=2025

Re-fetches only when the ABS release date is newer than the cached file.
'''

import hashlib
import json
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
 
import httpx
import pandas as pd
 
log = logging.getLogger(__name__)


BASE_URL = "https://data.api.abs.gov.au/rest"
CACHE_DIR = Path("data/raw/abs_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# API request params: exponential backoff with repeated failure
REQUEST_DELAY = 0.5
MAX_RETRY = 5
RETRY_BACKOFF = 2.0

DATASETS: dict[str, dict[str, str]] = {
    "erp_sa2": {
        "dataflow": "ABS_ANNUAL_ERP_ASGS2021", # (ASGS 2021 / Edition 3)
        # Dimensions: MEASURE . REGION TYPE . ASGS . FREQ . TIME PERIOD
        "key": "ERP.SA2..A",
        "description": "Estimated Resident Population by SA2, annual",
    },
}

# creates unique paths for cached data (first 12 characters in hex sequence)
def _cache_path(dataflow: str, key: str, params: dict) -> Path:
    fingerprint = hashlib.md5(
        f"{dataflow}:{key}:{json.dumps(params, sort_keys=True)}".encode()
    ).hexdigest()[:12]
    return CACHE_DIR / f"{dataflow}_{fingerprint}.parquet"

# Fetch specified sdmx-json data from ABS (coerced into dict)
def _fetch_sdmx_json(client: httpx.Client, url: str, params: dict) -> dict[str, Any]:
    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = client.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        # Retry request after error
        except httpx.HTTPStatusError as e:
            # 429: too many requests
            if e.response.status_code >= 429:
                wait = float(e.response.headers.get("Retry-After", 10))
                log.warning("Rate limited. Waiting %.0fs…", wait)
                time.sleep(wait)
                continue
            # 5**: server error
            if e.response.status_code >= 500 and attempt < MAX_RETRY:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                log.warning(
                    "HTTP %s on attempt %d/%d. Retrying in %.0fs…",
                    e.response.status_code, attempt, MAX_RETRY, wait,
                )
                time.sleep(wait)
                continue
            raise
        except httpx.TransportError as e:
            if attempt < MAX_RETRY:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                log.warning("Transport error: %s. Retrying in %.0fs…", e, wait)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRY} attempts")

# Parse sdmx-json into dataframe
'''
    The json data divides into two main sections:
        'structure': {
            'dimensions': {
                'series': [             dimension lookup tables (we expect only [2] (ASGS) to vary)
                'observation': [        time dimension lookup tables (ie [1] = 2021, [2] = 2022 ...)
        'datasets': [
            'series': {
                '0:0:14:0': {           series key
                    'observations': {
                        0: [4539.0]     observation key - [value]
                        1: [6827.0]

    Convert into dataframe:
        measure     region-type     sa2-code    freq    year    value
'''
def _parse_sdmx_json(payload: dict) -> pd.DataFrame:
    structure = payload["structure"]
    series_dims = structure["dimensions"]["series"]
    observation_dims = structure["dimensions"]["observation"]
    dataset = payload["dataSets"][0]["series"]

    # Lookups: flatten 'id' into an indexable 2d array [dimension][index]
    series_lookups = [[v["id"] for v in dim["values"]] for dim in series_dims]
    observation_lookups = [[v["id"] for v in dim["values"]] for dim in observation_dims]

    series_names = [dim["id"] for dim in series_dims]
    observation_names = [dim["id"] for dim in observation_dims]

    rows: list[dict] = []
    for series_key, series_data in dataset.items():
        # series_key: "0:2:14:0" (indices for each series dimension)
        s_indices = [int(i) for i in series_key.split(":")]
        s_values = {
            series_names[i]: series_lookups[i][s_indices[i]] for i in range(len(series_names))
        }
 
        for o_key, o_data in series_data["observations"].items():
            o_indices = [int(i) for i in o_key.split(":")]
            o_values = {
                observation_names[i]: observation_lookups[i][o_indices[i]]
                for i in range(len(observation_names))
            }
 
            value = o_data[0]  # first element is the primary value
            rows.append({**s_values, **o_values, "value": value})
 
    return pd.DataFrame(rows)

# Determine most recent ABS release date (none if not exposed)
def _abs_release_date(client: httpx.Client, dataflow: str) -> date | None:
    url = f"{BASE_URL}/dataflow/ABS/{dataflow}"
    try:
        payload = _fetch_sdmx_json(client, url, {"detail": "full"})
        # Release date lives in annotations when present
        annotations = (
            payload.get("dataflows", [{}])[0]
            .get("annotations", [])
        )
        for a in annotations:
            if a.get("type") == "ReleaseDate":
                return datetime.strptime(a["text"], "%Y-%m-%d").date()
    except Exception as e:
        log.debug("Could not retrieve release date for %s: %s", dataflow, e)
    return None

# Determine if the current cached file is up to date
def _cache_is_fresh(cache: Path, release: date | None) -> bool:
    if not cache.exists():
        return False
    if release is None:
        return True
    cache_date = datetime.fromtimestamp(cache.stat().st_mtime).date()
    return cache_date >= release

# API wrapper
'''
    Usage:
        client = ABSClient()
        erp_df = client.fetch("erp_sa2")
    Force a re-fetch ignoring cache:
        erp_df = client.fetch("erp_sa2", force=True)
'''
class ABSClient: 
    def __init__(self, base_url: str = BASE_URL, request_delay: float = REQUEST_DELAY):
        self._base_url = base_url.rstrip("/")
        self._delay = request_delay
        self._http = httpx.Client(
            headers={
                "Accept": "application/vnd.sdmx.data+json;version=1.0",
                "User-Agent": "purview_dashboard/0.1 (research; adeuchr@gmail.com)",
            }
        )
 
    def close(self) -> None:
        self._http.close()
 
    def __enter__(self):
        return self
 
    def __exit__(self, *args):
        self.close()

    # Reads from cache unless force=True or ABS has a newer release.
    def fetch(self, dataset: str, force: bool = False) -> pd.DataFrame:
        if dataset not in DATASETS:
            raise ValueError(
                f"Unknown dataset '{dataset}'. "
                f"Available: {list(DATASETS)}"
            )
 
        spec = DATASETS[dataset]
        dataflow = spec["dataflow"]
        key = spec["key"]
        params = {"startPeriod": "2016", "detail": "dataonly"}
 
        cache_file = _cache_path(dataflow, key, params)
 
        if not force:
            release_date = _abs_release_date(self._http, dataflow)
            if _cache_is_fresh(cache_file, release_date):
                log.info("Cache hit for %s (%s)", dataset, cache_file.name)
                return pd.read_parquet(cache_file)
 
        log.info("Fetching %s from ABS DataAPI…", dataset)
        url = f"{self._base_url}/data/{dataflow}/{key}"
        time.sleep(self._delay)
        payload = _fetch_sdmx_json(self._http, url, params)
 
        df = _parse_sdmx_json(payload["data"])

        df.to_parquet(cache_file, index=False)
        log.info(
            "Cached %d rows -> %s", len(df), cache_file.name
        )
        return df
 
    def fetch_all(self, force: bool = False) -> dict[str, pd.DataFrame]:
        # Fetch every configured dataset
        results = {}
        for name in DATASETS:
            results[name] = self.fetch(name, force=force)
        return results

# CLI helper
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
 
    with ABSClient() as client:
        for name, spec in DATASETS.items():
            print(f"\n--- {name}: {spec['description']} ---")
            try:
                df = client.fetch(name, force=True)
                #print(df.head())
                #print(f"Shape: {df.shape}")
            except Exception as e:
                print(f"ERROR: {e}")