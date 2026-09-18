"""Population and population growth, with no API key.

The Census Population Estimates Program publishes annual subcounty estimates
as an open CSV. No key, no signup. It covers incorporated places and minor
civil divisions, which are exactly the two geographies this screen uses.

Why this exists. ACS is richer: it carries households, tenure, income and age,
and this module replaces none of that. But ACS needs a key, and when that key
is absent or rejected the tool lost the demand pillar AND the supply pillar
(permits are expressed per household), AND the shortlist fell back to ranking
by distance. That is 55% of the weighting plus the selection rule, gone,
because of one credential. PEP removes that cliff: population and population
growth load with no key at all, the shortlist ranks properly, and the permits
metric gets a denominator.

# LIMITATIONS
- These are estimates, modelled forward from the 2020 census using births,
  deaths and migration indicators. They are not survey measurements and they
  are revised each year, including the back series.
- Population growth is not household growth. A town whose population grew
  because household size rose is not producing new rental demand at the same
  rate. Where ACS is available its household figures are the better measure and
  both are reported.
- Annexation is not adjusted for, same as ACS.
- The vintage matters: a 2024 vintage revises 2020 to 2023 as well, so figures
  will not match an older release.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from ..cache import FetchError
from ..context import Context
from ..provenance import MetricSpec, Unit, Value, missing

SOURCE_NAME = "Census Population Estimates Program, subcounty totals"
BASE = "https://www2.census.gov/programs-surveys/popest/datasets"

# The file moved directory between decades, so both shapes are tried. The
# vintage year is probed backwards from last year.
URL_PATTERNS = [
    "{base}/2020-{year}/cities/totals/sub-est{year}.csv",
    "{base}/2020-{year}/cities/totals/SUB-EST{year}.csv",
    "{base}/2020-{year}/cities/totals/sub-est{year}_all.csv",
]

# Summary levels in this file. 061 is a minor civil division, 162 an
# incorporated place. The others (county parts, consolidated cities) would
# double count, so they are skipped rather than summed.
SUMLEV_COUSUB = "061"
SUMLEV_PLACE = "162"

GROWTH_YEARS = 4          # 2020 base to the latest estimate is four intervals

METRICS = [
    MetricSpec("pop_cagr_pep", "Population CAGR, estimates", "demand", True, "%", 2,
               description="Compound annual population growth from the Census "
                           "Population Estimates Program. Needs no API key, and "
                           "is the fallback when ACS is unavailable."),
]

CONTEXT_COLUMNS = [
    MetricSpec("pep_population", "Population (estimate)", "demand", True, "", 0, scored=False),
    MetricSpec("pep_population_base", "Population, 2020 base", "demand", True, "", 0, scored=False),
    MetricSpec("pep_vintage", "Population estimate vintage", "demand", True, "", 0, scored=False),
]


def _norm(name: str) -> str:
    return name.strip().upper().replace("﻿", "")


def _fetch_latest(ctx: Context, max_back: int = 3) -> tuple[str, int, str, str]:
    """Return (csv text, vintage year, url, retrieved_at)."""
    errors = []
    start = date.today().year - 1
    for year in range(start, start - max_back - 1, -1):
        for pattern in URL_PATTERNS:
            url = pattern.format(base=BASE, year=year)
            try:
                resp = ctx.cache.get(url, key=f"pep_subest_{year}_{pattern[-12:]}",
                                     ttl_days=180)
            except FetchError as exc:
                errors.append(f"{url}: {exc}")
                continue
            text = resp.body.decode("latin-1", errors="replace")
            if "SUMLEV" not in text[:400].upper():
                errors.append(f"{url}: downloaded but has no SUMLEV column in its header")
                continue
            ctx.log(f"PEP: using the {year} vintage subcounty estimates")
            return text, year, url, resp.retrieved_at
    raise FetchError(
        "Census population estimates could not be downloaded. Tried:\n  "
        + "\n  ".join(errors)
        + "\nCheck the current path under "
        + "https://www2.census.gov/programs-surveys/popest/datasets/"
    )


def parse(text: str, url: str) -> dict[str, dict[str, float]]:
    """Return {geoid: {"latest": n, "base": n, "latest_year": y}}.

    GEOIDs are built the same way the rest of the tool builds them: state+place
    for a place, state+county+cousub for a minor civil division.
    """
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise FetchError(f"{url} has no header row")
    cols = {_norm(f): f for f in reader.fieldnames}

    for needed in ("SUMLEV", "STATE", "NAME"):
        if needed not in cols:
            raise FetchError(
                f"{url} is missing the '{needed}' column. Saw: {sorted(cols)}"
            )

    pop_years = sorted(
        int(name.replace("POPESTIMATE", ""))
        for name in cols
        if name.startswith("POPESTIMATE") and name.replace("POPESTIMATE", "").isdigit()
    )
    if not pop_years:
        raise FetchError(f"{url} has no POPESTIMATE columns. Saw: {sorted(cols)}")
    latest_year = pop_years[-1]
    base_col = cols.get("ESTIMATESBASE2020") or cols.get(f"POPESTIMATE{pop_years[0]}")

    out: dict[str, dict[str, float]] = {}
    for row in reader:
        sumlev = (row.get(cols["SUMLEV"]) or "").strip()
        state = (row.get(cols["STATE"]) or "").strip().zfill(2)
        if sumlev == SUMLEV_COUSUB:
            county = (row.get(cols.get("COUNTY", "")) or "").strip().zfill(3)
            cousub = (row.get(cols.get("COUSUB", "")) or "").strip().zfill(5)
            if not (county.isdigit() and cousub.isdigit()):
                continue
            geoid = state + county + cousub
        elif sumlev == SUMLEV_PLACE:
            place = (row.get(cols.get("PLACE", "")) or "").strip().zfill(5)
            if not place.isdigit():
                continue
            geoid = state + place
        else:
            continue

        def num(col_name):
            raw = (row.get(col_name) or "").strip().replace(",", "")
            try:
                return float(raw)
            except ValueError:
                return None

        latest = num(cols[f"POPESTIMATE{latest_year}"])
        base = num(base_col) if base_col else None
        if latest is None:
            continue
        out[geoid] = {"latest": latest, "base": base, "latest_year": latest_year}
    if not out:
        raise FetchError(f"{url} parsed but produced no place or MCD rows")
    return out


def collect(ctx: Context, units: list[Unit]) -> dict[str, dict[str, Value]]:
    try:
        text, vintage, url, retrieved = _fetch_latest(ctx)
        table = parse(text, url)
    except FetchError as exc:
        reason = str(exc).splitlines()[0]
        return {
            u.geoid: {
                "pop_cagr_pep": missing(reason, source=SOURCE_NAME),
                "pep_population": missing(reason, source=SOURCE_NAME),
                "pep_population_base": missing(reason, source=SOURCE_NAME),
                "pep_vintage": missing(reason, source=SOURCE_NAME),
            }
            for u in units
        }

    label = f"Population Estimates, {vintage} vintage"
    note = (
        "Modelled estimate, not a survey measurement, revised each year "
        "including the back series. Population growth is not household growth: "
        "where ACS is available its household figures are the better demand "
        "measure and both are reported."
    )

    out: dict[str, dict[str, Value]] = {}
    found = 0
    for unit in units:
        row = table.get(unit.geoid)
        if row is None:
            reason = "not in the Census subcounty population estimates file"
            out[unit.geoid] = {
                key: missing(reason, source=SOURCE_NAME, vintage=label, url=url)
                for key in ("pop_cagr_pep", "pep_population",
                            "pep_population_base", "pep_vintage")
            }
            continue
        found += 1

        def val(v, notes=note):
            return Value(v, source=SOURCE_NAME, vintage=label, url=url,
                         retrieved_at=retrieved, notes=notes)

        values = {
            "pep_population": val(row["latest"]),
            "pep_vintage": val(f"{vintage} vintage, estimate for {int(row['latest_year'])}"),
        }
        base = row["base"]
        if base and base > 0:
            values["pep_population_base"] = val(base)
            cagr = ((row["latest"] / base) ** (1.0 / GROWTH_YEARS) - 1.0) * 100.0
            values["pop_cagr_pep"] = val(
                round(cagr, 3),
                notes=f"2020 base to {int(row['latest_year'])}, {GROWTH_YEARS} "
                      f"intervals. " + note,
            )
        else:
            values["pep_population_base"] = missing(
                "2020 base population not reported", source=SOURCE_NAME, vintage=label)
            values["pop_cagr_pep"] = missing(
                "no 2020 base to compare against", source=SOURCE_NAME, vintage=label)
        out[unit.geoid] = values

    ctx.log(f"PEP: population matched for {found} of {len(units)} submarkets")
    return out


def population_by_geoid(values: dict[str, dict[str, Value]]) -> dict[str, float]:
    """Pull the population column out, for use as a ranking or denominator."""
    out: dict[str, float] = {}
    for geoid, row in values.items():
        cell = row.get("pep_population")
        if cell is not None and not cell.is_missing:
            try:
                out[geoid] = float(cell.value)
            except (TypeError, ValueError):
                continue
    return out
