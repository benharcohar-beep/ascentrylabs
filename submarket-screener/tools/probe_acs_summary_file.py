"""Probe the ACS table-based summary file layout from a machine that can reach Census.

The Data API needs a key as of 12 May 2026. The summary files on www2.census.gov
do not, and this tool already reads that host successfully for the Gazetteer,
the Building Permits Survey and the Population Estimates Program. If the tables
this screen needs are published there in a readable shape, the demand pillar
stops depending on a credential.

This prints what is actually there. It guesses nothing and it is not imported by
the screener: run it, read the output, then write the source module against what
came back. That is the same order that got the Building Permits layout right
after guessing it wrong twice.

    python tools/probe_acs_summary_file.py
"""
from __future__ import annotations

import sys
import urllib.request

# Tables this screen would need, and why each one.
TABLES = {
    "B01003": "total population",
    "B25003": "tenure, owner and renter occupied households",
    "B19013": "median household income",
    "B01001": "sex by age, for the 20 to 34 share",
    "B11001": "household type, for a household count cross-check",
}

BASE = "https://www2.census.gov/programs-surveys/acs/summary_file"
YEARS = [2024, 2023, 2022]

# Two published layouts, because Census changed the path more than once.
DATA_PATTERNS = [
    "{base}/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table}.dat",
    "{base}/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table_lower}.dat",
]
GEO_PATTERNS = [
    "{base}/{year}/table-based-SF/documentation/Geos{year}5YR.txt",
    "{base}/{year}/table-based-SF/geography/Geos{year}5YR.txt",
    "{base}/{year}/table-based-SF/documentation/geography/Geos{year}5YR.txt",
]


def peek(url: str, nbytes: int = 1400) -> None:
    """Fetch the first bytes of a URL and print them, or print why not."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "submarket-screener probe", "Range": f"bytes=0-{nbytes}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read(nbytes)
            size = response.headers.get("Content-Range") or response.headers.get("Content-Length")
            print(f"  OK   {response.status}  size={size}  {url}")
            for line in body.decode("utf-8", "replace").splitlines()[:4]:
                print(f"       | {line[:240]}")
    except Exception as exc:  # noqa: BLE001 - a probe reports, it does not judge
        print(f"  MISS {type(exc).__name__}: {str(exc)[:110]}  {url}")


def main() -> int:
    for year in YEARS:
        print(f"\n=== {year} 5-year ===")
        print(" geography file:")
        for pattern in GEO_PATTERNS:
            peek(pattern.format(base=BASE, year=year))
        print(" data files:")
        for table, why in TABLES.items():
            print(f"  [{table}] {why}")
            for pattern in DATA_PATTERNS:
                peek(pattern.format(base=BASE, year=year, table=table,
                                    table_lower=table.lower()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
