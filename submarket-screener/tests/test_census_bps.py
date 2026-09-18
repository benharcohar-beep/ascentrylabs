"""Offline tests for screener/sources/census_bps.py.

Nothing here touches the network. Every byte the module sees is either the
synthetic fixture in tests/fixtures/ or a string built in this file, served
through a fake cache that mimics screener.cache.Cache.get.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from screener.cache import CachedResponse, FetchError
from screener.provenance import Unit
from screener.sources import census_bps


FIXTURE_DIR = Path(__file__).parent / "fixtures"
PLACE_FIXTURE = FIXTURE_DIR / "bps_place_SYNTHETIC_mw2412y.txt"
FAKE_RETRIEVED_AT = "2026-01-15T09:30:00Z"

# Synthetic county file. Layout: 6 prefix fields then 4 (Bldgs, Units, Value)
# triples reported and 4 imputed, so 30 fields per row.
COUNTY_TEXT_SYNTHETIC = "\n".join(
    [
        "Survey,FIPS,FIPS,Region,Division,,1-unit,1-unit,1-unit,2-units,2-units,"
        "2-units,3-4 units,3-4 units,3-4 units,5+ units,5+ units,5+ units,"
        "1-unit,1-unit,1-unit,2-units,2-units,2-units,3-4 units,3-4 units,"
        "3-4 units,5+ units,5+ units,5+ units",
        "Date,State,County,Code,Code,County Name,Bldgs,Units,Value,Bldgs,Units,"
        "Value,Bldgs,Units,Value,Bldgs,Units,Value,Bldgs,Units,Value,Bldgs,"
        "Units,Value,Bldgs,Units,Value,Bldgs,Units,Value",
        ",,,,,,REPORTED,REPORTED,REPORTED,REPORTED,REPORTED,REPORTED,REPORTED,"
        "REPORTED,REPORTED,REPORTED,REPORTED,REPORTED,PUBLISHED,PUBLISHED,"
        "PUBLISHED,PUBLISHED,PUBLISHED,PUBLISHED,PUBLISHED,PUBLISHED,PUBLISHED,"
        "PUBLISHED,PUBLISHED,PUBLISHED",
        "2412,55,025,2,3,SYNTHETIC COUNTY A,100,200,20000000,5,10,1000000,3,12,"
        "1200000,40,300,45000000,100,200,20000000,5,10,1000000,3,12,1200000,"
        "40,300,45000000",
        "2412,55,021,2,3,SYNTHETIC COUNTY C,20,20,4000000,0,0,0,0,0,0,2,50,"
        "6000000,20,20,4000000,0,0,0,0,0,0,2,50,6000000",
    ]
)

# The winning probe year in every test below. _probe_start_year is patched so
# the suite does not change behaviour as the real calendar moves on.
PATCHED_PROBE_START = 2025
EXPECTED_YEARS = [2022, 2023, 2024]


# ---------------------------------------------------------------- test doubles


class FakeCache:
    """Stands in for screener.cache.Cache. Serves a dict of url -> text."""

    def __init__(self, files: dict[str, str]) -> None:
        self.files = files
        self.requested: list[str] = []

    def get(self, url: str, *, key: str, ttl_days: int | None = None, **kwargs):
        self.requested.append(url)
        if url not in self.files:
            raise FetchError(f"HTTP 404 from {url} :: Not Found")
        return CachedResponse(
            self.files[url].encode("utf-8"), FAKE_RETRIEVED_AT, url, True
        )


class FakeCtx:
    """collect() only ever touches ctx.cache and ctx.log."""

    def __init__(self, cache: FakeCache) -> None:
        self.cache = cache
        self.logs: list[str] = []

    def log(self, msg: str) -> None:
        self.logs.append(msg)


# --------------------------------------------------------------------- units

UNIT_CITY_A = Unit(
    geoid="5521375",
    name="Synthetic City A",
    geo_type="place",
    state_fips="55",
    county_fips="55025",
    county_name="Synthetic County A",
)
UNIT_TOWN_B = Unit(
    geoid="5502580500",
    name="Synthetic Town B",
    geo_type="county_subdivision",
    state_fips="55",
    county_fips="55025",
    county_name="Synthetic County A",
)
UNIT_VILLAGE_C = Unit(
    geoid="5512345",
    name="Synthetic Village C",
    geo_type="place",
    state_fips="55",
    county_fips="55021",
    county_name="Synthetic County C",
)
UNIT_ABSENT_D = Unit(
    geoid="5599999",
    name="Synthetic Village D (no permit office)",
    geo_type="place",
    state_fips="55",
    county_fips="55025",
    county_name="Synthetic County A",
)
UNIT_VILLAGE_E = Unit(
    geoid="5519999",
    name="Synthetic Village E (in the file, never filed a month)",
    geo_type="place",
    state_fips="55",
    county_fips="55025",
)

ALL_UNITS = [UNIT_CITY_A, UNIT_TOWN_B, UNIT_VILLAGE_C, UNIT_ABSENT_D, UNIT_VILLAGE_E]


# ------------------------------------------------------------------ fixtures


@pytest.fixture()
def place_text() -> str:
    return PLACE_FIXTURE.read_text()


@pytest.fixture()
def wired(monkeypatch, place_text):
    """A FakeCtx wired up with the fixture served for 2022, 2023 and 2024.

    2025 is deliberately absent so the backwards probe has to take a step.
    """
    monkeypatch.setattr(census_bps, "_probe_start_year", lambda: PATCHED_PROBE_START)
    files: dict[str, str] = {}
    for year in EXPECTED_YEARS:
        files[census_bps.place_url("mw", year)] = place_text
        files[census_bps.county_url(year)] = COUNTY_TEXT_SYNTHETIC
    return FakeCtx(FakeCache(files))


# ------------------------------------------------------------- url patterns


def test_place_url_pattern():
    assert census_bps.place_url("mw", 2024) == (
        "https://www2.census.gov/econ/bps/Place/Midwest%20Region/mw2412y.txt"
    )
    assert census_bps.place_url("so", 2023) == (
        "https://www2.census.gov/econ/bps/Place/South%20Region/so2312y.txt"
    )


def test_county_url_pattern():
    assert census_bps.county_url(2024) == (
        "https://www2.census.gov/econ/bps/County/co2412y.txt"
    )


def test_region_mapping_covers_the_shipped_markets():
    assert census_bps.STATE_FIPS_TO_REGION["55"][0] == "mw"   # Wisconsin
    assert census_bps.STATE_FIPS_TO_REGION["26"][0] == "mw"   # Michigan
    assert census_bps.STATE_FIPS_TO_REGION["21"][0] == "so"   # Kentucky
    assert census_bps.STATE_FIPS_TO_REGION["13"][0] == "so"   # Georgia
    # 50 states plus the District of Columbia.
    assert len(census_bps.STATE_FIPS_TO_REGION) == 51


# ------------------------------------------------------------------ parsing


def test_multi_line_header_is_skipped(place_text):
    rows = census_bps.parse_place_file(place_text, "SYNTHETIC")
    # Two header lines and a blank, then six data rows.
    assert len(rows) == 6
    assert rows[0].place_name == "SYNTHETIC CITY A"


def test_place_row_parses_and_joins_on_state_plus_place(place_text):
    rows = census_bps.parse_place_file(place_text, "SYNTHETIC")
    city_a = rows[0]
    assert city_a.state_fips == "55"
    assert city_a.place_key == "5521375"
    assert city_a.units_reported == (30, 4, 6, 120)
    assert city_a.reported_5plus == 120
    assert city_a.reported_total == 160
    assert city_a.imputed_total == 0


def test_mcd_row_joins_on_state_plus_county_plus_mcd(place_text):
    rows = census_bps.parse_place_file(place_text, "SYNTHETIC")
    town_b = next(r for r in rows if r.place_name == "SYNTHETIC TOWN B")
    # FIPS place code is 00000, so there is no place level join at all.
    assert town_b.place_key == ""
    assert town_b.cousub_key == "5502580500"
    assert town_b.reported_5plus == 50
    # Non zero imputed block: Census estimated a month this office did not file.
    assert town_b.imputed_5plus == 5
    assert town_b.imputed_total == 7


def test_zero_permit_row_is_a_real_zero(place_text):
    rows = census_bps.parse_place_file(place_text, "SYNTHETIC")
    village_c = next(r for r in rows if r.place_name == "SYNTHETIC VILLAGE C")
    assert village_c.place_key == "5512345"
    assert village_c.reported_total == 0
    assert village_c.reported_5plus == 0


def test_unmatched_row_has_no_join_key(place_text):
    rows = census_bps.parse_place_file(place_text, "SYNTHETIC")
    unmatched = next(r for r in rows if r.place_name == "UNINCORPORATED AREA D")
    assert unmatched.place_key == ""
    assert unmatched.cousub_key == ""
    # The permits are real, they just cannot be attributed to a jurisdiction.
    assert unmatched.reported_total == 48


def test_field_count_mismatch_raises_fetch_error(place_text):
    lines = place_text.splitlines()
    # Chop three fields off the first data row, as a layout change would.
    lines[3] = ",".join(lines[3].split(",")[:-3])
    broken = "\n".join(lines)
    with pytest.raises(FetchError) as excinfo:
        census_bps.parse_place_file(broken, "SYNTHETIC_BROKEN")
    msg = str(excinfo.value)
    assert "SYNTHETIC_BROKEN" in msg
    assert "38" in msg           # observed
    assert "41" in msg           # expected, with the published block
    assert "29" in msg           # expected, reported block only


def test_older_vintage_without_published_block_is_tolerated():
    """A vintage shipping the reported block only is 29 fields, not 41.

    With nothing to compare against, the reported figure is all there is, and
    the imputed portion is unknowable rather than zero. The parser carries the
    reported block through as the published one and reports no imputation,
    which is the only honest reading.
    """
    header = "Survey,State,6-Digit,County,Census Place,FIPS Place,FIPS MCD"
    row = (
        "201212,55,900001,025,54000,21375,21375,45000,357,31540,,,53590,2,3,12,"
        "OLD VINTAGE CITY,20,20,4000000,0,0,0,0,0,0,2,60,7000000"
    )
    rows = census_bps.parse_place_file(header + "\n" + row, "SYNTHETIC_OLD")
    assert len(rows) == 1
    assert rows[0].reported_5plus == 60
    assert rows[0].published_5plus == 60
    assert rows[0].imputed_total == 0
    assert rows[0].months_reported == 12


def test_empty_file_raises_fetch_error():
    with pytest.raises(FetchError):
        census_bps.parse_place_file("Survey,6-Digit,County\nDate,ID,Code\n", "EMPTY")


def test_county_file_parses():
    rows = census_bps.parse_county_file(COUNTY_TEXT_SYNTHETIC, "SYNTHETIC_COUNTY")
    assert len(rows) == 2
    assert rows[0].county_fips == "55025"
    assert rows[0].units_reported == (200, 10, 12, 300)
    assert rows[1].county_fips == "55021"
    assert rows[1].units_reported[3] == 50


# ------------------------------------------------------------ module surface


def test_metric_keys_and_directions():
    keys = [m.key for m in census_bps.METRICS]
    assert keys == ["permits_5plus_3y_per_1k_hh", "permits_total_3y_per_1k_hh"]
    assert all(m.pillar == "supply" for m in census_bps.METRICS)
    assert all(m.higher_is_better is False for m in census_bps.METRICS)
    ctx_keys = [c.key for c in census_bps.CONTEXT_COLUMNS]
    assert ctx_keys == [
        "permits_5plus_3y",
        "permits_total_3y",
        "permits_years",
        "permits_county_5plus_3y",
        "permits_place_share_of_county",
    ]
    assert all(c.scored is False for c in census_bps.CONTEXT_COLUMNS)


def test_no_long_dashes_in_module_source():
    src = Path(census_bps.__file__).read_text()
    assert chr(0x2013) not in src   # en dash
    assert chr(0x2014) not in src   # em dash


# ----------------------------------------------------------------- collect


def test_collect_returns_every_unit(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    assert set(out) == {u.geoid for u in ALL_UNITS}
    for cells in out.values():
        assert set(cells) == {
            "permits_5plus_3y_per_1k_hh",
            "permits_total_3y_per_1k_hh",
            "permits_5plus_3y",
            "permits_total_3y",
            "permits_years",
            "permits_county_5plus_3y",
            "permits_place_share_of_county",
        }


def test_collect_probes_backwards_to_the_latest_published_year(wired):
    census_bps.collect(wired, ALL_UNITS)
    # 2025 is missing from the fake server, so the probe falls back to 2024.
    assert census_bps.place_url("mw", 2025) in wired.cache.requested
    assert any("resolved to 2024" in m for m in wired.logs)
    assert any("2022, 2023, 2024" in m for m in wired.logs)


def test_collect_sums_three_years_and_multiple_permit_offices(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    city_a = out[UNIT_CITY_A.geoid]
    # Two permit offices (120 + 30 units in 5+ structures), three identical
    # year files, so 150 x 3.
    assert city_a["permits_5plus_3y"].value == 450
    assert city_a["permits_total_3y"].value == 570
    assert city_a["permits_years"].value == "2022, 2023, 2024"


def test_collect_carries_provenance_from_the_cached_response(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    cell = out[UNIT_CITY_A.geoid]["permits_5plus_3y"]
    assert cell.source == census_bps.SOURCE_NAME
    assert cell.retrieved_at == FAKE_RETRIEVED_AT
    assert "mw2412y.txt" in cell.url
    assert "2022, 2023, 2024" in cell.vintage


def test_collect_per_1k_needs_the_acs_household_base(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    cell = out[UNIT_CITY_A.geoid]["permits_5plus_3y_per_1k_hh"]
    assert cell.is_missing
    assert cell.missing_reason == "household base not available from ACS"


def test_collect_computes_per_1k_when_households_supplied(wired):
    out = census_bps.collect(wired, ALL_UNITS, households={UNIT_CITY_A.geoid: 10000})
    city_a = out[UNIT_CITY_A.geoid]
    assert city_a["permits_5plus_3y_per_1k_hh"].value == pytest.approx(45.0)
    assert city_a["permits_total_3y_per_1k_hh"].value == pytest.approx(57.0)
    # A unit absent from the households map still falls back to MISSING.
    assert out[UNIT_TOWN_B.geoid]["permits_5plus_3y_per_1k_hh"].is_missing


def test_collect_joins_a_county_subdivision_and_flags_imputation(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    town_b = out[UNIT_TOWN_B.geoid]
    # Town B files 10 of 12 months, so the published block exceeds the reported
    # one. The published figure is what goes out: 55 units in 5+ structures a
    # year over three years, not the 50 it actually filed.
    assert town_b["permits_5plus_3y"].value == 165
    assert town_b["permits_total_3y"].value == 201
    notes = town_b["permits_5plus_3y"].notes
    assert "imputed" in notes.lower()
    assert "includes them" in notes
    assert "30 of 36 possible office months" in notes


def test_collect_case_a_reported_zero_is_zero_not_missing(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    village_c = out[UNIT_VILLAGE_C.geoid]
    assert village_c["permits_5plus_3y"].value == 0
    assert village_c["permits_5plus_3y"].is_missing is False
    assert "reported zero" in village_c["permits_5plus_3y"].notes


def test_collect_case_b_absent_place_is_missing_not_zero(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    absent = out[UNIT_ABSENT_D.geoid]
    cell = absent["permits_5plus_3y"]
    assert cell.is_missing
    assert cell.value is None
    assert cell.missing_reason == (
        "not a permit-issuing place in BPS; permits are likely issued by the county"
    )
    # The years used are still reported, so the workbook can explain itself.
    assert absent["permits_years"].value == "2022, 2023, 2024"
    # And the county reconciliation still shows what the county did permit.
    assert absent["permits_county_5plus_3y"].value == 900


def test_collect_case_c_download_failure_is_missing_with_the_error(monkeypatch, place_text):
    monkeypatch.setattr(census_bps, "_probe_start_year", lambda: PATCHED_PROBE_START)
    ctx = FakeCtx(FakeCache({}))          # server has nothing at all
    out = census_bps.collect(ctx, ALL_UNITS)
    for cells in out.values():
        for cell in cells.values():
            assert cell.is_missing
            assert "404" in cell.missing_reason or "download failed" in cell.missing_reason


def test_collect_case_c_partial_window_failure_is_missing(monkeypatch, place_text):
    """One of the three years is unavailable, so the 3 year sum is refused."""
    monkeypatch.setattr(census_bps, "_probe_start_year", lambda: PATCHED_PROBE_START)
    files = {
        census_bps.place_url("mw", 2024): place_text,
        census_bps.place_url("mw", 2023): place_text,
        # 2022 missing on purpose.
        census_bps.county_url(2024): COUNTY_TEXT_SYNTHETIC,
        census_bps.county_url(2023): COUNTY_TEXT_SYNTHETIC,
        census_bps.county_url(2022): COUNTY_TEXT_SYNTHETIC,
    }
    ctx = FakeCtx(FakeCache(files))
    out = census_bps.collect(ctx, ALL_UNITS)
    cell = out[UNIT_CITY_A.geoid]["permits_5plus_3y"]
    assert cell.is_missing
    assert "2022" in cell.missing_reason


def test_collect_county_reconciliation_and_share(wired):
    out = census_bps.collect(wired, ALL_UNITS)
    # County 55025: 300 units in 5+ structures per year, three years.
    assert out[UNIT_CITY_A.geoid]["permits_county_5plus_3y"].value == 900
    # Screened places in 55025 that matched: City A (450) and Town B (165).
    share = out[UNIT_CITY_A.geoid]["permits_place_share_of_county"].value
    assert share == pytest.approx(615 / 900)
    # Same value for every unit in the county, county level column.
    assert out[UNIT_TOWN_B.geoid]["permits_place_share_of_county"].value == pytest.approx(
        615 / 900
    )
    # County 55021: 50 per year x 3, and Village C permitted nothing.
    assert out[UNIT_VILLAGE_C.geoid]["permits_county_5plus_3y"].value == 150
    assert out[UNIT_VILLAGE_C.geoid]["permits_place_share_of_county"].value == 0.0


def test_collect_logs_unmatched_permit_office_units(wired):
    census_bps.collect(wired, ALL_UNITS)
    unmatched_logs = [m for m in wired.logs if "could not be joined" in m]
    assert unmatched_logs, wired.logs
    # 8 single family plus 40 in 5+ structures, three year files.
    assert "144 permitted units" in unmatched_logs[0]


def test_collect_unmapped_state_is_missing(wired):
    odd = Unit(
        geoid="7812345",
        name="Somewhere Offshore",
        geo_type="place",
        state_fips="78",          # US Virgin Islands, not in the BPS regions
        county_fips="78010",
    )
    out = census_bps.collect(wired, ALL_UNITS + [odd])
    cell = out["7812345"]["permits_5plus_3y"]
    assert cell.is_missing
    assert "78" in cell.missing_reason


def test_collect_with_no_units_returns_empty(wired):
    assert census_bps.collect(wired, []) == {}


# ---------------------------------------------------------------------------
# The fifth case: in the file, zero permits, and zero months reported.
#
# Only the Number of Months Reported column separates this from a genuine
# reported zero. Without it, a jurisdiction whose permit office simply never
# filed looks like the quietest, least supplied submarket in the market, and
# because supply is scored low is good it climbs the ranking on the strength
# of its own silence.
# ---------------------------------------------------------------------------


def test_months_reported_is_parsed(place_text):
    rows = census_bps.parse_place_file(place_text, "SYNTHETIC")
    by_name = {r.place_name: r for r in rows}
    assert by_name["SYNTHETIC CITY A"].months_reported == 12
    assert by_name["SYNTHETIC TOWN B"].months_reported == 10
    assert by_name["SYNTHETIC VILLAGE E"].months_reported == 0


def test_a_jurisdiction_that_never_filed_is_missing_not_a_reported_zero(wired):
    out = census_bps.collect(wired, ALL_UNITS, households={"5519999": 1000.0})
    village_e = out[UNIT_VILLAGE_E.geoid]

    # The raw count is still published as context, because it is what the file
    # says, with a note explaining what it does and does not mean.
    assert village_e["permits_5plus_3y"].value == 0
    assert "absence of reporting" in village_e["permits_5plus_3y"].notes

    # But the scored metrics refuse to treat that zero as a supply measurement,
    # even though a household base was supplied.
    for key in ("permits_5plus_3y_per_1k_hh", "permits_total_3y_per_1k_hh"):
        cell = village_e[key]
        assert cell.is_missing, f"{key} should not be scored"
        assert "silence" in cell.missing_reason


def test_a_full_reporter_with_zero_permits_is_still_a_real_zero(wired):
    """The contrast case. Village C filed all twelve months and built nothing."""
    out = census_bps.collect(wired, ALL_UNITS, households={"5512345": 1000.0})
    village_c = out[UNIT_VILLAGE_C.geoid]
    assert village_c["permits_5plus_3y"].value == 0
    assert village_c["permits_5plus_3y"].is_missing is False
    assert "reported zero" in village_c["permits_5plus_3y"].notes
    assert village_c["permits_5plus_3y_per_1k_hh"].value == 0.0
