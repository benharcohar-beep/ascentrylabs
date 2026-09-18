"""Census names the county a place is in. It never numbers it.

Savannah's first live run had every county level column MISSING: employment
growth, all three unemployment columns, and both permit reconciliation columns,
which is 18 of the 108 points inside demand, on two of the four markets. The
cause was this reader looking for a county FIPS column, finding none, and
giving up.

The header, taken from the live server on 2026-09-18 rather than assumed:

    STATE|STATEFP|PLACEFP|PLACENS|PLACENAME|TYPE|CLASSFP|FUNCSTAT|COUNTIES
    GA|13|00184|02403056|Abbeville city|INCORPORATED PLACE|C1|A|Wilcox County

The name to FIPS resolution comes from the market config, which lists every
county with both, so there is no second file to fetch and nothing else to 404.
"""
from __future__ import annotations

import pytest

from screener.cache import FetchError
from screener.sources.census_place_county import _parse

# Savannah's three counties, exactly as savannah_ga.yml spells them.
SAVANNAH_COUNTIES = {
    "Chatham County": "13051",
    "Effingham County": "13103",
    "Bryan County": "13029",
}

HEADER_2020 = ("STATE|STATEFP|PLACEFP|PLACENS|PLACENAME|TYPE|CLASSFP|"
               "FUNCSTAT|COUNTIES\n")


def row(place: str, name: str, counties: str, state: str = "13",
        abbrev: str = "GA") -> str:
    return (f"{abbrev}|{state}|{place}|02403056|{name}|INCORPORATED PLACE|"
            f"C1|A|{counties}\n")


def test_a_named_county_resolves_to_its_fips():
    text = HEADER_2020 + row("62104", "Pooler city", "Chatham County")
    assert _parse(text, SAVANNAH_COUNTIES) == {"1362104": ("13051", "Chatham County")}


def test_the_geoid_is_state_plus_place_and_matches_the_gazetteer_form():
    text = HEADER_2020 + row("62104", "Pooler city", "Chatham County")
    geoid = next(iter(_parse(text, SAVANNAH_COUNTIES)))
    assert geoid == "1362104"
    assert len(geoid) == 7          # 2 + 5, as the rest of the tool builds it


def test_a_place_outside_the_market_counties_is_left_out():
    """It is about to be filtered out anyway, and inventing a FIPS for it would
    attach another county's jobs figures to a submarket that is not screened.

    Paired with an in-market place on purpose: a file of nothing but outsiders
    is a different case, covered below, and conflating the two would let a
    total matching failure pass as ordinary filtering.
    """
    text = (HEADER_2020
            + row("00408", "Acworth city", "Cobb County")
            + row("62104", "Pooler city", "Chatham County"))
    assert _parse(text, SAVANNAH_COUNTIES) == {
        "1362104": ("13051", "Chatham County"),
    }


def test_a_straddling_place_prefers_a_county_the_market_covers():
    """Taking whichever Census listed first would drop the place at the county
    filter, for a reason invisible to anyone reading the output."""
    text = HEADER_2020 + row("65044", "Richmond Hill city",
                             "Liberty County, Bryan County")
    assert _parse(text, SAVANNAH_COUNTIES) == {
        "1365044": ("13029", "Bryan County"),
    }


def test_a_straddling_place_inside_two_covered_counties_takes_the_first():
    text = HEADER_2020 + row("71184", "Somewhere city",
                             "Chatham County, Effingham County")
    assert _parse(text, SAVANNAH_COUNTIES)["1371184"][0] == "13051"


def test_county_spelling_is_matched_case_and_space_insensitively():
    text = HEADER_2020 + row("62104", "Pooler city", "  chatham COUNTY ")
    assert _parse(text, SAVANNAH_COUNTIES)["1362104"][0] == "13051"


def test_the_2010_file_shape_still_works():
    """Column called COUNTY, and blank lines between rows."""
    text = ("STATE|STATEFP|PLACEFP|PLACENAME|TYPE|FUNCSTAT|COUNTY\n"
            "\n"
            "GA|13|62104|Pooler city|Incorporated Place|A|Chatham County\n"
            "\n")
    assert _parse(text, SAVANNAH_COUNTIES) == {"1362104": ("13051", "Chatham County")}


def test_an_explicit_county_fips_column_is_still_preferred_when_present():
    """If Census ever publishes the number, use it rather than matching text."""
    text = ("STATE|STATEFP|PLACEFP|PLACENAME|COUNTYFP|COUNTYNAME\n"
            "GA|13|62104|Pooler city|051|Chatham County\n")
    assert _parse(text, SAVANNAH_COUNTIES) == {"1362104": ("13051", "Chatham County")}


def test_matching_nothing_at_all_is_an_error_not_an_empty_screen():
    """Silently returning nothing looks identical to a market with no places,
    and the run would carry on and report every county column MISSING without
    saying that the crosswalk itself is what broke."""
    text = HEADER_2020 + row("00408", "Acworth city", "Cobb County")
    with pytest.raises(FetchError) as caught:
        _parse(text, {})
    assert "names counties rather than numbering them" in str(caught.value)


def test_a_file_with_no_county_column_at_all_is_rejected():
    text = "STATE|STATEFP|PLACEFP|PLACENAME\nGA|13|62104|Pooler city\n"
    with pytest.raises(FetchError) as caught:
        _parse(text, SAVANNAH_COUNTIES)
    assert "county" in str(caught.value).lower()
