"""American Community Survey 5-year estimates: the demand pillar.

Two vintages are pulled for every market:

  latest    the most recent 5-year release the API will serve
  prior     exactly five years earlier, so the two samples do NOT overlap

That non-overlap matters. ACS 5-year estimates pool five years of interviews.
Comparing the 2020-2024 release with the 2021-2025 release compares two samples
that share four years of data, so almost any difference is noise. The Census
Bureau's own guidance is to compare non-overlapping periods, which is why the
growth rates here are 2015-2019 versus 2020-2024 and are described as such in
the workbook.

We also pull the margin of error on population and households and report
whether the change is statistically distinguishable from zero at roughly 90%
confidence, which is the ACS standard. A growth rate that is not significant is
still shown, but it is flagged, because presenting a 1.2% growth rate for a
village of 3,000 people as if it were a fact is exactly the mistake an
acquisitions VP will catch.

# LIMITATIONS
- Small geographies have wide margins of error. For a township of 4,000 people
  the 90% confidence interval on population can be plus or minus 8%.
- Municipal boundaries change. A place that annexed land between the two
  vintages will show growth that is partly annexation, not new households.
- 5-year estimates lag. The 2020-2024 release is centred on 2022, so it is
  already three to four years stale for a market moving fast.
- Median household income is a place-wide figure and says nothing about the
  income of renter households specifically, which is what actually underwrites
  a rent roll.
"""
from __future__ import annotations

import json
import math
from datetime import date

from ..cache import FetchError, require_key
from ..context import Context
from ..provenance import MetricSpec, Unit, Value, missing

SOURCE_NAME = "Census ACS 5-Year Estimates API"
BASE = "https://api.census.gov/data"
KEY_SIGNUP = "https://api.census.gov/data/key_signup.html"
KEY_HELP = (
    "Request a free Census API key at "
    "https://api.census.gov/data/key_signup.html . It arrives by email in a "
    "minute or two and you have to click the activation link."
)

# ACS uses large negative sentinels for "cannot be computed" rather than a null.
# -666666666 is the most common (median of an empty or open-ended distribution).
# Treating one of these as a real number would be a catastrophic silent error.
ACS_SENTINELS = {
    -666666666, -999999999, -888888888, -222222222,
    -333333333, -555555555, -99999999,
}

# Age 20 to 34, the renter formation cohort, summed from B01001.
_MALE_20_34 = ["B01001_008E", "B01001_009E", "B01001_010E", "B01001_011E", "B01001_012E"]
_FEMALE_20_34 = ["B01001_032E", "B01001_033E", "B01001_034E", "B01001_035E", "B01001_036E"]

LATEST_VARS = [
    "B01003_001E", "B01003_001M",       # total population and its margin of error
    "B11001_001E", "B11001_001M",       # households and margin of error
    "B25003_001E", "B25003_003E",       # occupied units, renter occupied
    "B19013_001E",                      # median household income
    "B25064_001E",                      # median gross rent
    "B01002_001E",                      # median age
] + _MALE_20_34 + _FEMALE_20_34

PRIOR_VARS = ["B01003_001E", "B01003_001M", "B11001_001E", "B11001_001M"]

METRICS = [
    MetricSpec("pop_cagr_5y", "Population CAGR, 5yr", "demand", True, "%", 2,
               description="Compound annual growth in population between two non-overlapping ACS 5-year releases."),
    MetricSpec("hh_cagr_5y", "Household CAGR, 5yr", "demand", True, "%", 2,
               description="Compound annual growth in households. The truer demand signal for rental units."),
    MetricSpec("renter_share", "Renter share of occupied units", "demand", True, "%", 1,
               description="Renter-occupied divided by total occupied housing units."),
    MetricSpec("median_hh_income", "Median household income", "demand", True, "$", 0,
               description="Higher income supports higher achievable rent and lower bad debt."),
    MetricSpec("age_20_34_share", "Share aged 20 to 34", "demand", True, "%", 1,
               description="The prime renter formation cohort."),
]

CONTEXT_COLUMNS = [
    MetricSpec("population", "Population", "demand", True, "", 0, scored=False),
    MetricSpec("households", "Households", "demand", True, "", 0, scored=False),
    MetricSpec("population_prior", "Population, prior vintage", "demand", True, "", 0, scored=False),
    MetricSpec("households_prior", "Households, prior vintage", "demand", True, "", 0, scored=False),
    MetricSpec("pop_growth_significant", "Population change significant at 90%", "demand", True, "", 0, scored=False),
    MetricSpec("hh_growth_significant", "Household change significant at 90%", "demand", True, "", 0, scored=False),
    MetricSpec("median_age", "Median age", "demand", True, "", 1, scored=False),
    MetricSpec("median_gross_rent_acs", "Median gross rent (ACS)", "rent", True, "$", 0, scored=False),
    MetricSpec("renter_households", "Renter households", "demand", True, "", 0, scored=False),
    MetricSpec("acs_vintage_latest", "ACS vintage (latest)", "demand", True, "", 0, scored=False),
    MetricSpec("acs_vintage_prior", "ACS vintage (prior)", "demand", True, "", 0, scored=False),
]


def _clean(raw) -> float | None:
    """Turn an ACS API string into a number, or None if it is not usable."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text in ("", "null", "None", "-", "*", "**", "N", "(X)"):
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if int(num) in ACS_SENTINELS:
        return None
    # ACS publishes a margin of error of -555555555 for "estimate is controlled",
    # already caught above. No ACS count, median or margin of error is ever
    # legitimately negative, so anything still negative here is a code we do
    # not recognise and must not be treated as a figure. Letting -1 through
    # would be particularly bad: a margin of error of -1 squares to 1 and would
    # make almost any change read as statistically significant.
    if num < 0:
        return None
    return num


def _explain_non_json(year: int, cache_key: str, text: str) -> str:
    """Say what actually went wrong, not just that the body was not JSON.

    The Census API answers a bad key with HTTP 200 and an HTML page, so a naive
    reader reports "no release answered" and sends you hunting for a vintage
    problem that does not exist. The page title says exactly what is wrong.
    """
    lowered = text.lower()
    if "<title>invalid key</title>" in lowered:
        return (
            f"ACS {year}: the Census API rejected the key (its reply is an HTML "
            f"page titled 'Invalid Key'). Two usual causes: the key was never "
            f"activated, so open the signup email from the Census Data API "
            f"Service and click the activation link in it; or the key was "
            f"mistyped. Copy it straight from that email and rerun "
            f"setup_keys.py. Nothing is wrong with the ACS vintage."
        )
    if "<title>missing key</title>" in lowered:
        return (
            f"ACS {year}: no key reached the API. Check CENSUS_API_KEY is set in "
            f".env, then rerun setup_keys.py. Get a free key at {KEY_SIGNUP}."
        )
    if "<html" in lowered[:400]:
        title = ""
        if "<title>" in lowered:
            start = lowered.index("<title>") + 7
            title = text[start:start + 80].split("<")[0].strip()
        return (
            f"ACS {year} returned an HTML page instead of JSON for {cache_key}"
            + (f", titled '{title}'" if title else "")
            + f". First 200 characters: {text[:200]}"
        )
    return f"ACS {year} returned a non-JSON body for {cache_key}: {text[:200]}"


def _vintage_label(year: int) -> str:
    return f"ACS {year - 4}-{year} 5-year"


def _query(ctx: Context, year: int, variables: list[str], geo_clause: dict, key: str,
           cache_key: str) -> tuple[list, str]:
    url = f"{BASE}/{year}/acs/acs5"
    params: dict[str, object] = {"get": ",".join(["NAME"] + variables)}
    params.update(geo_clause)
    params["key"] = key
    resp = ctx.cache.get(url, key=cache_key, params=params, ttl_days=90)
    text = resp.text.lstrip()
    if not text.startswith("["):
        # The Census API answers a bad key with HTTP 200 and an HTML page, so
        # the cache has just stored an error page as if it were data. Drop it,
        # or activating the key would change nothing until the TTL expired.
        ctx.cache.forget(cache_key)
        raise FetchError(_explain_non_json(year, cache_key, text))
    try:
        return json.loads(text), resp.retrieved_at
    except json.JSONDecodeError as exc:
        ctx.cache.forget(cache_key)
        raise FetchError(f"ACS {year} returned malformed JSON for {cache_key}: {exc}") from exc


def _geo_clauses(ctx: Context) -> list[tuple[str, dict]]:
    """One API call per county for subdivisions, one per state for places."""
    market = ctx.market
    if market.geo_type == "county_subdivision":
        clauses = []
        for county in market.counties:
            fips = county["fips"]
            clauses.append((
                fips,
                {"for": "county subdivision:*", "in": [f"state:{fips[:2]}", f"county:{fips[2:]}"]},
            ))
        return clauses
    return [(state, {"for": "place:*", "in": f"state:{state}"}) for state in market.states]


def _rows_to_map(payload: list[list[str]], geo_type: str) -> dict[str, dict[str, str]]:
    """Index an ACS response by GEOID, which the API returns as trailing columns."""
    header, *rows = payload
    idx = {name: i for i, name in enumerate(header)}
    if geo_type == "county_subdivision":
        needed = ["state", "county", "county subdivision"]
    else:
        needed = ["state", "place"]
    for col in needed:
        if col not in idx:
            raise FetchError(
                f"ACS response is missing the '{col}' geography column. "
                f"Columns returned: {header}"
            )
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        geoid = "".join(row[idx[c]].zfill(3 if c == "county" else (2 if c == "state" else 5))
                        for c in needed)
        out[geoid] = {name: row[i] for name, i in idx.items()}
    return out


def find_latest_vintage(ctx: Context, key: str, max_back: int = 4) -> int:
    """Probe backwards for the newest ACS 5-year release the API will serve."""
    market = ctx.market
    probe_state = market.states[0]
    errors = []
    start = date.today().year - 1
    for year in range(start, start - max_back - 1, -1):
        try:
            _query(
                ctx, year, ["B01003_001E"],
                {"for": "state:" + probe_state}, key,
                f"acs_probe_{year}_{probe_state}",
            )
            ctx.log(f"ACS: latest available vintage is {_vintage_label(year)}")
            return year
        except FetchError as exc:
            errors.append(f"{year}: {exc}")
    joined = "\n  ".join(errors)
    if all("rejected the key" in e for e in errors):
        raise FetchError(
            "The Census API rejected your key on every vintage, so this is a "
            "key problem and not a vintage problem. Activate the key using the "
            "link in the Census signup email, or recopy it from that email and "
            "rerun setup_keys.py.\n  " + joined
        )
    raise FetchError(
        "No ACS 5-year release answered in the last "
        f"{max_back + 1} years.\n  " + joined
    )


def collect(ctx: Context, units: list[Unit]) -> dict[str, dict[str, Value]]:
    key = require_key("CENSUS_API_KEY", KEY_HELP)
    latest_year = find_latest_vintage(ctx, key)
    prior_year = latest_year - 5          # non-overlapping five-year samples

    latest_map: dict[str, dict[str, str]] = {}
    prior_map: dict[str, dict[str, str]] = {}
    retrieved_latest = retrieved_prior = ""
    latest_url = f"{BASE}/{latest_year}/acs/acs5"
    prior_url = f"{BASE}/{prior_year}/acs/acs5"
    prior_error = ""

    for tag, clause in _geo_clauses(ctx):
        payload, retrieved_latest = _query(
            ctx, latest_year, LATEST_VARS, clause, key,
            f"acs_{latest_year}_{ctx.market.key}_{tag}",
        )
        latest_map.update(_rows_to_map(payload, ctx.market.geo_type))

        try:
            payload, retrieved_prior = _query(
                ctx, prior_year, PRIOR_VARS, clause, key,
                f"acs_{prior_year}_{ctx.market.key}_{tag}",
            )
            prior_map.update(_rows_to_map(payload, ctx.market.geo_type))
        except FetchError as exc:
            prior_error = str(exc)
            ctx.log(f"WARNING: prior ACS vintage {prior_year} failed for {tag}: {exc}")

    latest_label = _vintage_label(latest_year)
    prior_label = _vintage_label(prior_year)

    def val(v, *, vintage=latest_label, url=latest_url, retrieved=None, notes="") -> Value:
        return Value(v, source=SOURCE_NAME, vintage=vintage, url=url,
                     retrieved_at=retrieved or retrieved_latest, notes=notes)

    out: dict[str, dict[str, Value]] = {}
    for unit in units:
        row: dict[str, Value] = {}
        rec = latest_map.get(unit.geoid)
        prev = prior_map.get(unit.geoid)

        if rec is None:
            reason = f"not returned by the ACS API for {latest_label}"
            for spec in METRICS + CONTEXT_COLUMNS:
                row[spec.key] = missing(reason, source=SOURCE_NAME,
                                        vintage=latest_label, url=latest_url)
            out[unit.geoid] = row
            continue

        row["acs_vintage_latest"] = val(latest_label)
        row["acs_vintage_prior"] = val(prior_label, vintage=prior_label, url=prior_url,
                                       retrieved=retrieved_prior)

        pop = _clean(rec.get("B01003_001E"))
        pop_moe = _clean(rec.get("B01003_001M"))
        hh = _clean(rec.get("B11001_001E"))
        hh_moe = _clean(rec.get("B11001_001M"))
        occ = _clean(rec.get("B25003_001E"))
        renter = _clean(rec.get("B25003_003E"))
        income = _clean(rec.get("B19013_001E"))
        gross_rent = _clean(rec.get("B25064_001E"))
        med_age = _clean(rec.get("B01002_001E"))

        row["population"] = val(pop) if pop is not None else missing(
            "population not reported", source=SOURCE_NAME, vintage=latest_label)
        row["households"] = val(hh) if hh is not None else missing(
            "households not reported", source=SOURCE_NAME, vintage=latest_label)
        row["median_age"] = val(med_age) if med_age is not None else missing(
            "median age not reported", source=SOURCE_NAME, vintage=latest_label)
        row["median_gross_rent_acs"] = (
            val(gross_rent,
                notes="ACS median gross rent includes utilities and covers the whole "
                      "occupied rental stock, old and new. It sits well below asking "
                      "rent on new product and is here only as a sanity check.")
            if gross_rent is not None
            else missing("median gross rent not reported", source=SOURCE_NAME,
                         vintage=latest_label)
        )
        row["renter_households"] = val(renter) if renter is not None else missing(
            "renter households not reported", source=SOURCE_NAME, vintage=latest_label)

        # --- renter share ---
        if occ and renter is not None and occ > 0:
            row["renter_share"] = val(round(100.0 * renter / occ, 2))
        else:
            row["renter_share"] = missing(
                "occupied housing units not reported or zero",
                source=SOURCE_NAME, vintage=latest_label)

        # --- median household income ---
        row["median_hh_income"] = (
            val(income) if income is not None else
            missing("median household income suppressed or not computable "
                    "(ACS returns a sentinel for small or open-ended distributions)",
                    source=SOURCE_NAME, vintage=latest_label)
        )

        # --- age 20 to 34 share ---
        parts = [_clean(rec.get(v)) for v in _MALE_20_34 + _FEMALE_20_34]
        if pop and pop > 0 and all(p is not None for p in parts):
            row["age_20_34_share"] = val(
                round(100.0 * sum(parts) / pop, 2),
                notes="Sum of B01001 male and female age bands 20 to 34, divided by "
                      "total population.")
        else:
            row["age_20_34_share"] = missing(
                "one or more B01001 age bands not reported",
                source=SOURCE_NAME, vintage=latest_label)

        # --- growth, prior vintage ---
        def growth(cur, cur_moe, old, old_moe, label_key, sig_key, what):
            if prev is None:
                reason = (f"prior vintage {prior_label} not available"
                          + (f": {prior_error}" if prior_error else ""))
                row[label_key] = missing(reason, source=SOURCE_NAME, vintage=prior_label)
                row[sig_key] = missing(reason, source=SOURCE_NAME, vintage=prior_label)
                return
            if cur is None or old is None or old <= 0:
                row[label_key] = missing(
                    f"{what} not reported in one of the two vintages",
                    source=SOURCE_NAME, vintage=prior_label)
                row[sig_key] = missing("cannot test significance without both estimates",
                                       source=SOURCE_NAME, vintage=prior_label)
                return
            cagr = ((cur / old) ** (1.0 / 5.0) - 1.0) * 100.0
            row[label_key] = val(
                round(cagr, 3),
                notes=(f"{latest_label} versus {prior_label}. The two samples do not "
                       f"overlap, which is the Census Bureau's own guidance for "
                       f"comparing 5-year estimates. Boundary changes such as "
                       f"annexation are not adjusted for."),
            )
            if cur_moe is None or old_moe is None:
                row[sig_key] = missing("margin of error not reported for one vintage",
                                       source=SOURCE_NAME, vintage=prior_label)
            else:
                # ACS margins are at 90% confidence. The margin on a difference is
                # the root of the sum of squares of the two margins.
                diff = cur - old
                diff_moe = math.sqrt(cur_moe ** 2 + old_moe ** 2)
                row[sig_key] = val(
                    "yes" if abs(diff) > diff_moe else "no",
                    notes=(f"Change of {diff:,.0f} against a 90% margin of error on "
                           f"the change of plus or minus {diff_moe:,.0f}. 'no' means "
                           f"the change is inside sampling noise and the growth rate "
                           f"should not be leaned on."),
                )

        old_pop = _clean(prev.get("B01003_001E")) if prev else None
        old_pop_moe = _clean(prev.get("B01003_001M")) if prev else None
        old_hh = _clean(prev.get("B11001_001E")) if prev else None
        old_hh_moe = _clean(prev.get("B11001_001M")) if prev else None

        row["population_prior"] = (
            Value(old_pop, source=SOURCE_NAME, vintage=prior_label, url=prior_url,
                  retrieved_at=retrieved_prior)
            if old_pop is not None else
            missing(f"not available in {prior_label}", source=SOURCE_NAME, vintage=prior_label)
        )
        row["households_prior"] = (
            Value(old_hh, source=SOURCE_NAME, vintage=prior_label, url=prior_url,
                  retrieved_at=retrieved_prior)
            if old_hh is not None else
            missing(f"not available in {prior_label}", source=SOURCE_NAME, vintage=prior_label)
        )

        growth(pop, pop_moe, old_pop, old_pop_moe,
               "pop_cagr_5y", "pop_growth_significant", "population")
        growth(hh, hh_moe, old_hh, old_hh_moe,
               "hh_cagr_5y", "hh_growth_significant", "households")

        out[unit.geoid] = row

    return out
