"""Probe published file layouts from a machine that can reach the hosts.

Two file sets, one reason. Each is read by a module that had to be written
without being able to open the file, and each has already cost a run:

  1. ACS table-based summary files on www2.census.gov. The Data API needs a key
     as of 12 May 2026; these do not, and this tool already reads that host for
     the Gazetteer, the Building Permits Survey and the Population Estimates.
  2. NCES CCD staff file. The first live run found it is long format, one row
     per (LEAID, STAFF category), with a TOTAL_INDICATOR column, so the reader
     needs the actual category labels rather than a guess at them.

This prints what is there and guesses nothing. It is not imported by the
screener. Write the reader against the output, which is the order that got the
Building Permits layout right after two confident wrong attempts.

    python tools/probe_acs_summary_file.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

BASE = "https://www2.census.gov/programs-surveys/acs/summary_file"
DATA_URL = "{base}/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table}.dat"
GEO_URL = "{base}/{year}/table-based-SF/documentation/Geos{year}5YR.txt"

# Tables this screen would need, and why each one.
TABLES = {
    "b01003": "total population",
    "b25003": "tenure, owner and renter occupied households",
    "b19013": "median household income",
    "b01001": "sex by age, for the 20 to 34 share",
    "b01002": "median age",
    "b25064": "median gross rent",
}

# 2022 to 2024 are confirmed present. The prior vintage for a non-overlapping
# five-year comparison against 2024 is 2019, so that is the one that matters.
YEARS_TO_CONFIRM = [2021, 2020, 2019, 2018]

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"


def fetch(url: str, nbytes: int | None = 1400, timeout: int = 60) -> bytes | None:
    headers = {"User-Agent": "submarket-screener probe"}
    if nbytes is not None:
        headers["Range"] = f"bytes=0-{nbytes}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            size = response.headers.get("Content-Range") or response.headers.get("Content-Length")
            print(f"  OK   {response.status}  size={size}  {url}")
            return response.read() if nbytes is None else response.read(nbytes)
    except Exception as exc:  # noqa: BLE001 - a probe reports, it does not judge
        print(f"  MISS {type(exc).__name__}: {str(exc)[:110]}  {url}")
        return None


def show(body: bytes | None, lines: int = 3, width: int = 240) -> None:
    if body is None:
        return
    for line in body.decode("utf-8", "replace").splitlines()[:lines]:
        print(f"       | {line[:width]}")


def section_prior_vintages() -> None:
    print("\n=== 1. Which earlier vintages exist in the table-based layout ===")
    for year in YEARS_TO_CONFIRM:
        print(f" {year}:")
        show(fetch(GEO_URL.format(base=BASE, year=year)), lines=1, width=120)
        for table in ("b01003", "b25003"):
            show(fetch(DATA_URL.format(base=BASE, year=year, table=table)), lines=2, width=120)


def section_geo_file(year: int = 2024) -> None:
    print(f"\n=== 2. Geography file {year}: full header and real subdivision rows ===")
    print(" full header (first 12000 bytes):")
    head = fetch(GEO_URL.format(base=BASE, year=year), nbytes=12000)
    if head is None:
        return
    header = head.decode("utf-8", "replace").lstrip("﻿").splitlines()[0]
    columns = header.split("|")
    print(f"  {len(columns)} columns:")
    for i, name in enumerate(columns):
        print(f"    [{i:>2}] {name}")

    print(" whole file, looking for Wisconsin county subdivisions (SUMLEVEL 060) and places (160):")
    body = fetch(GEO_URL.format(base=BASE, year=year), nbytes=None, timeout=300)
    if body is None:
        return
    idx = {name: i for i, name in enumerate(columns)}
    found = {"060": 0, "160": 0, "050": 0}
    shown = Counter()
    for line in body.decode("utf-8", "replace").splitlines()[1:]:
        parts = line.split("|")
        if len(parts) < len(columns):
            continue
        if parts[idx["STATE"]] != "55":
            continue
        level = parts[idx["SUMLEVEL"]]
        if level in found:
            found[level] += 1
            if shown[level] < 3:
                shown[level] += 1
                keep = ["SUMLEVEL", "STATE", "COUNTY", "COUSUB", "PLACE"]
                keep += [c for c in columns if "GEO" in c.upper() or "NAME" in c.upper()]
                print("    " + "  ".join(f"{c}={parts[idx[c]]!r}" for c in keep if c in idx))
    print(f"  Wisconsin rows by summary level: {found}")


def section_data_row_shape(year: int = 2024) -> None:
    print(f"\n=== 3. Data file {year}: does GEO_ID match the geography file's id column ===")
    body = fetch(DATA_URL.format(base=BASE, year=year, table="b01003"), nbytes=None, timeout=300)
    if body is None:
        return
    lines = body.decode("utf-8", "replace").splitlines()
    print(f"  {len(lines) - 1:,} data rows. Rows whose GEO_ID starts with 0600000US55 (WI subdivisions):")
    hits = [ln for ln in lines[1:] if ln.startswith("0600000US55")]
    print(f"  {len(hits):,} found")
    for ln in hits[:3]:
        print(f"       | {ln}")
    print("  Rows starting 1600000US55 (WI places):")
    hits = [ln for ln in lines[1:] if ln.startswith("1600000US55")]
    print(f"  {len(hits):,} found")
    for ln in hits[:2]:
        print(f"       | {ln}")


def section_other_tables(year: int = 2024) -> None:
    print(f"\n=== 4. The other tables {year}: headers ===")
    for table, why in TABLES.items():
        print(f"  [{table}] {why}")
        show(fetch(DATA_URL.format(base=BASE, year=year, table=table)), lines=1, width=400)


def _first_table_in_zip(data: bytes, depth: int = 0) -> bytes | None:
    archive = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in archive.namelist() if not n.startswith("__MACOSX")]
    for name in names:
        if name.lower().endswith((".csv", ".txt")):
            return archive.read(name)
    nested = sorted((n for n in names if n.lower().endswith(".zip")),
                    key=lambda n: (0 if "csv" in n.lower() else 1, n))
    for name in nested:
        if depth < 3:
            found = _first_table_in_zip(archive.read(name), depth + 1)
            if found is not None:
                return found
    return None


def section_ccd_staff() -> None:
    print("\n=== 5. CCD staff file: the category labels the reader needs ===")
    candidates = sorted(CACHE.glob("ccd_lea_staff__*.bin"))
    if not candidates:
        print("  no cached staff file under", CACHE)
        return
    path = candidates[-1]
    print(f"  reading {path.name}")
    table = _first_table_in_zip(path.read_bytes())
    if table is None:
        print("  no table found inside the archive")
        return
    text = table.decode("utf-8", "replace")
    lines = text.splitlines()
    header = lines[0].lstrip("﻿").split(",")
    print(f"  header: {header}")
    idx = {name: i for i, name in enumerate(header)}
    import csv as _csv
    reader = _csv.reader(io.StringIO(text))
    next(reader)
    staff_values: Counter = Counter()
    indicator_values: Counter = Counter()
    example_rows = []
    for row in reader:
        if len(row) < len(header):
            continue
        staff_values[row[idx["STAFF"]]] += 1
        indicator_values[row[idx["TOTAL_INDICATOR"]]] += 1
        if row[idx["LEAID"]] == "5508520" and len(example_rows) < 40:
            example_rows.append(row)
    print("  distinct STAFF values:")
    for value, n in staff_values.most_common():
        print(f"    {n:>7}  {value!r}")
    print("  distinct TOTAL_INDICATOR values:")
    for value, n in indicator_values.most_common():
        print(f"    {n:>7}  {value!r}")
    print("  every row for LEAID 5508520 (Madison Metropolitan), STAFF | STAFF_COUNT | TOTAL_INDICATOR:")
    for row in example_rows:
        print(f"    {row[idx['STAFF']]!r:<45} {row[idx['STAFF_COUNT']]!r:<12} {row[idx['TOTAL_INDICATOR']]!r}")


def section_ccd_lunch() -> None:
    print("\n=== 6. CCD school lunch file: does it exist and what is its header ===")
    base = "https://nces.ed.gov/ccd/Data/zip"
    for name in ("ccd_sch_033_2223_l_1a_071823.zip", "ccd_sch_033_2122_l_1a_071722.zip",
                 "ccd_sch_033_2021_l_1a_080621.zip"):
        url = f"{base}/{name}"
        body = fetch(url, nbytes=None, timeout=300)
        if body is None:
            continue
        table = _first_table_in_zip(body)
        if table is None:
            print("  no table inside")
            continue
        text = table.decode("utf-8", "replace")
        lines = text.splitlines()
        print(f"  {len(lines) - 1:,} rows. header: {lines[0][:400]}")
        header = lines[0].lstrip("﻿").split(",")
        idx = {n: i for i, n in enumerate(header)}
        import csv as _csv
        reader = _csv.reader(io.StringIO(text))
        next(reader)
        lunch: Counter = Counter()
        indicator: Counter = Counter()
        wi_rows = []
        for row in reader:
            if len(row) < len(header):
                continue
            if "LUNCH_PROGRAM" in idx:
                lunch[row[idx["LUNCH_PROGRAM"]]] += 1
            if "TOTAL_INDICATOR" in idx:
                indicator[row[idx["TOTAL_INDICATOR"]]] += 1
            if row[idx.get("LEAID", 0)] == "5508520" and len(wi_rows) < 12:
                wi_rows.append(row)
        print("  distinct LUNCH_PROGRAM values:", dict(lunch))
        print("  distinct TOTAL_INDICATOR values:", dict(indicator))
        print("  first rows for LEAID 5508520:")
        for row in wi_rows:
            print("    " + " | ".join(row)[:300])
        break


def main() -> int:
    section_prior_vintages()
    section_geo_file()
    section_data_row_shape()
    section_other_tables()
    section_ccd_staff()
    section_ccd_lunch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
