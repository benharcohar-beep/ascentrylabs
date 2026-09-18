"""Tests for the keyless population source.

The point of this module is that it removes a single point of failure: before
it existed, an absent or rejected Census API key cost the demand pillar, the
supply pillar (permits are per household) and the shortlist selection rule all
at once. These pin the parsing and the GEOID construction, because a GEOID
built differently from the rest of the tool would silently match nothing.
"""
from __future__ import annotations

import pytest

from screener.cache import FetchError
from screener.sources import census_pep

# Real column names and summary levels, invented figures.
HEADER = (
    "SUMLEV,STATE,COUNTY,PLACE,COUSUB,CONCIT,PRIMGEO_FLAG,FUNCSTAT,NAME,STNAME,"
    "ESTIMATESBASE2020,POPESTIMATE2020,POPESTIMATE2021,POPESTIMATE2022,"
    "POPESTIMATE2023,POPESTIMATE2024"
)
ROWS = [
    # A Wisconsin minor civil division: state 55, county 025, cousub 80500.
    "061,55,025,00000,80500,00000,0,A,Verona town,Wisconsin,"
    "8000,8010,8200,8400,8600,8800",
    # An incorporated place: state 55, place 21375.
    "162,55,000,21375,00000,00000,0,A,Verona city,Wisconsin,"
    "14000,14100,14600,15100,15600,16000",
    # A summary level we must skip, or places get double counted.
    "157,55,025,21375,00000,00000,0,A,Verona city (part),Wisconsin,"
    "14000,14100,14600,15100,15600,16000",
    # A row with no base population.
    "162,55,000,99999,00000,00000,0,A,Nowhere village,Wisconsin,"
    ",,,,,2500",
]
TEXT = "\n".join([HEADER] + ROWS) + "\n"


def test_parses_mcd_and_place_geoids_the_same_way_the_rest_of_the_tool_does():
    table = census_pep.parse(TEXT, "SYNTHETIC")
    # state(2) + county(3) + cousub(5)
    assert "5502580500" in table
    # state(2) + place(5)
    assert "5521375" in table
    assert table["5502580500"]["latest"] == 8800
    assert table["5521375"]["base"] == 14000


def test_skips_summary_levels_that_would_double_count():
    table = census_pep.parse(TEXT, "SYNTHETIC")
    # The 157 county-part row describes the same city as the 162 row. Only one
    # of them may survive, and it must be the place-level figure.
    assert table["5521375"]["latest"] == 16000
    assert len(table) == 3


def test_a_row_with_no_base_still_parses_but_cannot_grow():
    table = census_pep.parse(TEXT, "SYNTHETIC")
    assert table["5599999"]["latest"] == 2500
    assert table["5599999"]["base"] is None


def test_a_file_with_no_popestimate_columns_raises():
    broken = "SUMLEV,STATE,NAME\n162,55,Somewhere\n"
    with pytest.raises(FetchError) as exc:
        census_pep.parse(broken, "SYNTHETIC_BROKEN")
    assert "POPESTIMATE" in str(exc.value)


def test_a_file_missing_sumlev_raises_rather_than_guessing():
    broken = "STATE,NAME,POPESTIMATE2024\n55,Somewhere,100\n"
    with pytest.raises(FetchError) as exc:
        census_pep.parse(broken, "SYNTHETIC_BROKEN")
    assert "SUMLEV" in str(exc.value)


def test_growth_is_computed_over_the_right_number_of_intervals():
    table = census_pep.parse(TEXT, "SYNTHETIC")
    row = table["5502580500"]
    expected = ((row["latest"] / row["base"]) ** (1 / census_pep.GROWTH_YEARS) - 1) * 100
    # 8000 to 8800 over four intervals is a shade under 2.4% a year.
    assert expected == pytest.approx(2.4, abs=0.1)


def test_population_by_geoid_skips_missing_cells():
    from screener.provenance import Value, missing

    values = {
        "a": {"pep_population": Value(1000.0, source="x")},
        "b": {"pep_population": missing("not in file")},
        "c": {},
    }
    assert census_pep.population_by_geoid(values) == {"a": 1000.0}
