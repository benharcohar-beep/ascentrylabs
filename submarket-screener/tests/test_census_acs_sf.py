"""The ACS summary file reader, tested against the bytes Census actually serves.

Every fixture line here is copied from the output of
tools/probe_acs_summary_file.py run against www2.census.gov, not invented. The
Building Permits reader was written twice from a plausible guess about the
layout and was wrong both times, so this one is pinned to observed bytes.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from screener.cache import FetchError
from screener.sources import census_acs_sf as sf

# Observed 2026-09-18 from acsdt5y2024-b01003.dat, first data rows for Wisconsin.
REAL_B01003 = (
    "GEO_ID|B01003_E001|B01003_M001\n"
    "0600000US5500100275|2050|265\n"
    "0600000US5500100300|1347|172\n"
    "0600000US5500107300|1279|240\n"
)
REAL_B25003 = (
    "GEO_ID|B25003_E001|B25003_M001|B25003_E002|B25003_M002|B25003_E003|B25003_M003\n"
    "0600000US5500100275|800|40|600|30|200|20\n"
)


class FakeCache:
    def __init__(self, bodies: dict[str, str]):
        self.bodies = bodies
        self.asked: list[tuple[str, tuple[str, ...]]] = []

    def get_filtered_lines(self, url, *, key, prefixes, ttl_days=90, max_bytes=None):
        self.asked.append((url, prefixes))
        for fragment, body in self.bodies.items():
            if fragment in url:
                return SimpleNamespace(text=body, retrieved_at="2026-09-18T00:00:00Z",
                                       url=url)
        raise FetchError(f"HTTP 404 from {url}")


def make_ctx(bodies, geo_type="county_subdivision", states=("55",)):
    return SimpleNamespace(
        cache=FakeCache(bodies),
        market=SimpleNamespace(geo_type=geo_type, states=list(states), key="madison_wi"),
        log=lambda _: None,
    )


def test_the_file_spelling_is_translated_to_the_api_spelling():
    """The file writes B01003_E001 where the API writes B01003_001E.

    The computation is written against the API's spelling. If this translation
    is wrong the columns silently come back empty, because the lookup misses
    rather than raising.
    """
    assert sf._api_name("B01003_E001") == "B01003_001E"
    assert sf._api_name("B01003_M001") == "B01003_001M"
    assert sf._api_name("B25003_E003") == "B25003_003E"
    assert sf._api_name("B01001_M010") == "B01001_010M"
    # Not a variable column, left alone.
    assert sf._api_name("GEO_ID") == "GEO_ID"


def test_geoid_is_the_part_after_US_and_matches_this_tools_convention():
    """0600000US5500100275 is state 55, county 001, subdivision 00275.

    The rest of the tool builds that GEOID as state + county + cousub, so the
    suffix has to match byte for byte or nothing joins.
    """
    assert sf._geoid_from("0600000US5500100275") == "5500100275"
    assert sf._geoid_from("1600000US5500100") == "5500100"
    assert len(sf._geoid_from("0600000US5500100275")) == 10   # 2 + 3 + 5
    assert len(sf._geoid_from("1600000US5500100")) == 7       # 2 + 5


def test_a_real_row_parses_into_api_named_variables():
    ctx = make_ctx({"b01003": REAL_B01003})
    rows, url, at = sf._read_table(ctx, 2024, "b01003", ("0600000US55",))
    assert rows["5500100275"] == {"B01003_001E": "2050", "B01003_001M": "265"}
    assert at == "2026-09-18T00:00:00Z"
    assert "acsdt5y2024-b01003.dat" in url


def test_only_the_states_in_play_are_requested():
    """The files are national. Asking for the whole country would download
    hundreds of megabytes to read one state."""
    ctx = make_ctx({"b01003": REAL_B01003})
    units = [SimpleNamespace(geoid="5500100275"), SimpleNamespace(geoid="5502500")]
    assert sf._state_prefixes(ctx, units) == ("0600000US55",)

    ctx_places = make_ctx({"b01003": REAL_B01003}, geo_type="place")
    multi = [SimpleNamespace(geoid="1305000"), SimpleNamespace(geoid="4503000")]
    assert sf._state_prefixes(ctx_places, multi) == ("1600000US13", "1600000US45")


def test_a_short_row_is_an_error_rather_than_a_silent_column_shift():
    """Zipping a short row against the header would slide every value one
    column left, so a margin of error would be read as an estimate."""
    broken = (
        "GEO_ID|B25003_E001|B25003_M001|B25003_E002|B25003_M002|B25003_E003|B25003_M003\n"
        "0600000US5500100275|800|40|600\n"
    )
    ctx = make_ctx({"b25003": broken})
    with pytest.raises(FetchError) as caught:
        sf._read_table(ctx, 2024, "b25003", ("0600000US55",))
    assert "4 fields against 7" in str(caught.value)


def test_a_header_that_is_not_geo_id_first_is_rejected():
    ctx = make_ctx({"b01003": "SOMETHING|ELSE\n1|2\n"})
    with pytest.raises(FetchError) as caught:
        sf._read_table(ctx, 2024, "b01003", ("0600000US55",))
    assert "GEO_ID" in str(caught.value)


def test_the_vintage_is_probed_and_the_newest_answer_wins():
    """Only 2024 answers, so 2024 is used even though newer years are tried."""
    calls = []

    def bodies_for(url, **kw):
        calls.append(url)
        if "acsdt5y2024-b01003" in url:
            return SimpleNamespace(text=REAL_B01003, retrieved_at="x", url=url)
        raise FetchError(f"HTTP 404 from {url}")

    ctx = make_ctx({})
    ctx.cache.get_filtered_lines = bodies_for
    assert sf._probe_year(ctx, ("0600000US55",)) == 2024
    assert any("acsdt5y2025" in c for c in calls), "it never tried a newer year"


def test_the_two_hundred_megabyte_age_table_failing_does_not_lose_the_others():
    """b01001 is worth 10 of 108 points inside demand. Everything else in the
    pillar is already downloaded by the time it is attempted, and losing one
    column must not cost the pillar."""
    ctx = make_ctx({"b01003": REAL_B01003, "b25003": REAL_B25003})
    merged, url, at, skipped = sf._collect_year(
        ctx, 2024, ["b01003", "b25003", "b01001"], ("0600000US55",)
    )
    assert merged["5500100275"]["B01003_001E"] == "2050"
    assert merged["5500100275"]["B25003_003E"] == "200"
    assert "b01001" in skipped
    assert url and at


def test_a_small_table_failing_is_still_fatal():
    """Total population missing is not a degraded run, it is no run. Reporting
    a partial demand pillar as though it were measured would be worse."""
    ctx = make_ctx({"b25003": REAL_B25003})
    with pytest.raises(FetchError):
        sf._collect_year(ctx, 2024, ["b01003", "b25003"], ("0600000US55",))


def test_an_unknown_geography_is_refused_rather_than_guessed():
    ctx = make_ctx({}, geo_type="tract")
    with pytest.raises(FetchError) as caught:
        sf._state_prefixes(ctx, [SimpleNamespace(geoid="55001000100")])
    assert "tract" in str(caught.value)
