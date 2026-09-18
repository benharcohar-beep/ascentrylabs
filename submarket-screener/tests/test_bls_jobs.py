"""Offline tests for screener/sources/bls_jobs.py.

Nothing here touches the network. Every byte comes from a synthetic fixture in
tests/fixtures/ whose filename contains SYNTHETIC so nobody mistakes it for a
real BLS download.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from screener.cache import CachedResponse, FetchError, MissingCredential  # noqa: E402
from screener.config import MarketConfig, Weights  # noqa: E402
from screener.context import Context  # noqa: E402
from screener.provenance import Unit, Value  # noqa: E402
from screener.sources import bls_jobs  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The whole test suite pretends today is this date, so probing back from
# "current year minus 1" always lands on 2025 and the CAGR base year on 2022,
# no matter which calendar year the suite is actually run in.
FROZEN_TODAY = datetime.date(2026, 6, 1)
LATEST_YEAR = 2025
BASE_YEAR = 2022

COUNTY = "26081"
RATE_SERIES = "LAUCN260810000000003"
LF_SERIES = "LAUCN260810000000006"

RETRIEVED_AT = "2026-06-01T09:15:00Z"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _FrozenDate(datetime.date):
    """Stand in for datetime.date inside the module under test."""

    @classmethod
    def today(cls) -> datetime.date:
        return FROZEN_TODAY


class FakeCache:
    """Stands in for screener.cache.Cache. Serves fixtures, records calls.

    `responses` maps a URL to either a string body or a callable taking the
    URL and returning a body. Returning the sentinel NOT_PUBLISHED makes the
    fake raise FetchError, which is how a 404 for an unpublished QCEW year
    reaches the module in real life.
    """

    NOT_PUBLISHED = object()

    def __init__(self, responses: dict) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def get(self, url, *, key, params=None, headers=None, method="GET",
            json_body=None, ttl_days=30, expect_content_type=None):
        self.calls.append(
            {"url": url, "key": key, "method": method, "json_body": json_body,
             "ttl_days": ttl_days}
        )
        handler = self.responses.get(url, self.NOT_PUBLISHED)
        if callable(handler):
            handler = handler(url)
        if handler is self.NOT_PUBLISHED:
            raise FetchError(f"HTTP 404 from {url} :: Not Found")
        return CachedResponse(
            handler.encode("utf-8"), RETRIEVED_AT, url, from_cache=False
        )


def qcew_url(year: int, fips5: str = COUNTY) -> str:
    return bls_jobs.QCEW_AREA_CSV_URL.format(year=year, fips5=fips5)


def make_context(cache: FakeCache) -> Context:
    market = MarketConfig(
        key="synthetic",
        name="Synthetic Market",
        short_name="Synthetic",
        states=["26"],
        counties=[{"fips": COUNTY, "name": "SYNTHETIC County", "state": "26"}],
        geo_type="county_subdivision",
        geo_type_reason="test",
        employment_centers=[],
    )
    weights = Weights(pillars={"demand": 1.0}, metrics={})
    return Context(
        cache=cache,
        market=market,
        weights=weights,
        output_dir=Path("/tmp"),
        verbose=False,
    )


def make_units() -> list[Unit]:
    return [
        Unit(geoid="2608112345", name="Alpha Township",
             geo_type="county_subdivision", state_fips="26",
             county_fips=COUNTY, county_name="SYNTHETIC County"),
        Unit(geoid="2608167890", name="Beta Township",
             geo_type="county_subdivision", state_fips="26",
             county_fips=COUNTY, county_name="SYNTHETIC County"),
    ]


@pytest.fixture(autouse=True)
def _frozen_clock_and_key(monkeypatch):
    monkeypatch.setattr(bls_jobs, "date", _FrozenDate)
    monkeypatch.setenv("BLS_API_KEY", "SYNTHETIC-TEST-KEY-0000")


def laus_responses(body: str) -> dict:
    return {bls_jobs.BLS_API_V2_URL: body}


def happy_responses() -> dict:
    responses = {
        qcew_url(LATEST_YEAR): fixture("qcew_area_SYNTHETIC_26081_2025_valid.csv"),
        qcew_url(BASE_YEAR): fixture("qcew_area_SYNTHETIC_26081_2022_valid.csv"),
    }
    responses.update(laus_responses(fixture("bls_laus_SYNTHETIC_success.json")))
    return responses


# --------------------------------------------------------------- module shape


def test_module_surface_matches_the_contract():
    assert isinstance(bls_jobs.SOURCE_NAME, str) and bls_jobs.SOURCE_NAME
    assert callable(bls_jobs.collect)

    metrics = {m.key: m for m in bls_jobs.METRICS}
    assert set(metrics) == {"county_emp_cagr_3y", "county_unemployment_rate"}
    assert all(m.pillar == "demand" for m in bls_jobs.METRICS)
    assert all(m.scored for m in bls_jobs.METRICS)
    assert metrics["county_emp_cagr_3y"].higher_is_better is True
    assert metrics["county_emp_cagr_3y"].unit == "%"
    assert metrics["county_unemployment_rate"].higher_is_better is False
    assert metrics["county_unemployment_rate"].unit == "%"

    context = {m.key: m for m in bls_jobs.CONTEXT_COLUMNS}
    assert set(context) == {
        "county_employment_latest", "county_employment_year",
        "county_labor_force", "county_unemployment_year",
    }
    assert all(m.scored is False for m in bls_jobs.CONTEXT_COLUMNS)
    assert all(m.pillar == "demand" for m in bls_jobs.CONTEXT_COLUMNS)


def test_module_source_has_no_em_or_en_dashes():
    src = (PROJECT_ROOT / "screener" / "sources" / "bls_jobs.py").read_text(
        encoding="utf-8"
    )
    # chr(8212) is the em dash, chr(8211) the en dash. Referenced by
    # codepoint so this test file does not itself contain one.
    assert chr(8212) not in src
    assert chr(8211) not in src


# ----------------------------------------------------------- series ID shape


def test_series_id_length_is_the_documented_laus_layout():
    """A county LAUS series ID is 20 characters, not 18.

    The brief for this module described an 18 character ID built from
    'LAU' + 'CN' + FIPS5 + 7 zeros + 2 digit measure. That recipe is
    internally inconsistent (it produces 19 characters) and it does not match
    the published LAUS layout, which is 'LA' + seasonal code + a 15 character
    area code ('CN' + FIPS5 + 8 zeros) + a 2 character measure code, so 20
    characters in total. This test pins the real layout and records why it is
    not 18, because a wrong series ID makes BLS return an empty series with
    HTTP 200 rather than an error.
    """
    series_id = bls_jobs.build_laus_series_id(COUNTY, "03")
    assert series_id == RATE_SERIES
    assert len(series_id) == 20
    assert len(series_id) == bls_jobs.LAUS_SERIES_ID_LENGTH
    assert len(series_id) != 18

    # Structural breakdown, so a future edit cannot quietly move a field.
    assert series_id[:3] == "LAU"
    assert series_id[3:5] == "CN"
    assert series_id[5:10] == COUNTY
    assert series_id[10:18] == "00000000"
    assert series_id[18:] == "03"


def test_series_id_measure_codes():
    assert bls_jobs.build_laus_series_id(COUNTY, "06") == LF_SERIES
    assert bls_jobs.build_laus_series_id(COUNTY, "05").endswith("05")
    assert bls_jobs.build_laus_series_id(COUNTY, "04").endswith("04")


@pytest.mark.parametrize(
    "fips5, measure",
    [("2608", "03"), ("260811", "03"), ("2608A", "03"), (COUNTY, "3"), (COUNTY, "abc")],
)
def test_series_id_refuses_to_build_a_malformed_id(fips5, measure):
    with pytest.raises(ValueError):
        bls_jobs.build_laus_series_id(fips5, measure)


# --------------------------------------------------------------- QCEW parser


def test_qcew_parser_reads_the_total_covered_row():
    row = bls_jobs.parse_qcew_annual_csv(
        fixture("qcew_area_SYNTHETIC_26081_2025_valid.csv"),
        COUNTY, LATEST_YEAR, qcew_url(LATEST_YEAR),
    )
    assert row.employment == 350000
    assert row.suppressed is False
    assert row.problem == ""
    assert row.year == LATEST_YEAR


def test_qcew_parser_flags_a_suppressed_row_and_never_returns_zero():
    row = bls_jobs.parse_qcew_annual_csv(
        fixture("qcew_area_SYNTHETIC_26081_suppressed.csv"),
        COUNTY, LATEST_YEAR, qcew_url(LATEST_YEAR),
    )
    # The fixture publishes annual_avg_emplvl as 0 alongside disclosure_code N,
    # which is exactly the trap: a naive parser reports a county with no jobs.
    assert row.suppressed is True
    assert row.employment is None
    assert "suppressed by BLS disclosure rules" in row.problem


def test_qcew_parser_reports_a_missing_total_row():
    row = bls_jobs.parse_qcew_annual_csv(
        fixture("qcew_area_SYNTHETIC_26081_no_total.csv"),
        COUNTY, LATEST_YEAR, qcew_url(LATEST_YEAR),
    )
    assert row.employment is None
    assert row.suppressed is False
    assert "no total covered row" in row.problem


def test_qcew_parser_raises_on_a_changed_layout():
    with pytest.raises(FetchError) as exc:
        bls_jobs.parse_qcew_annual_csv(
            fixture("qcew_area_SYNTHETIC_26081_bad_layout.csv"),
            COUNTY, LATEST_YEAR, qcew_url(LATEST_YEAR),
        )
    message = str(exc.value)
    assert qcew_url(LATEST_YEAR) in message
    assert "annual_avg_emplvl" in message
    assert "disclosure_code" in message


def test_qcew_parser_raises_when_the_file_year_disagrees():
    with pytest.raises(FetchError) as exc:
        bls_jobs.parse_qcew_annual_csv(
            fixture("qcew_area_SYNTHETIC_26081_2025_valid.csv"),
            COUNTY, 2024, qcew_url(2024),
        )
    assert "2024" in str(exc.value)


def test_qcew_parser_ignores_other_counties_in_the_file():
    row = bls_jobs.parse_qcew_annual_csv(
        fixture("qcew_area_SYNTHETIC_26081_2025_valid.csv"),
        "26999", LATEST_YEAR, qcew_url(LATEST_YEAR),
    )
    assert row.employment == 11111


def test_compute_cagr():
    assert bls_jobs.compute_cagr(320000, 350000, 3) == pytest.approx(3.0321, abs=1e-3)
    # A zero or negative base has no defined growth rate, and we refuse to
    # invent one rather than dividing by zero.
    assert bls_jobs.compute_cagr(0, 350000, 3) is None
    assert bls_jobs.compute_cagr(-5, 350000, 3) is None


# --------------------------------------------------------------- LAUS parser


def test_laus_parser_takes_the_annual_average_observation():
    observations = bls_jobs.parse_laus_response(
        fixture("bls_laus_SYNTHETIC_success.json"), bls_jobs.BLS_API_V2_URL
    )
    assert set(observations) == {RATE_SERIES, LF_SERIES}
    # M06 for 2025 is newer than M13 for 2024 but it is a month, not the annual
    # average, so it must be ignored.
    assert observations[RATE_SERIES].year == 2024
    assert observations[RATE_SERIES].value == pytest.approx(4.1)
    assert observations[LF_SERIES].year == 2024
    assert observations[LF_SERIES].value == pytest.approx(350123.0)


def test_laus_parser_raises_when_status_is_not_request_succeeded():
    with pytest.raises(FetchError) as exc:
        bls_jobs.parse_laus_response(
            fixture("bls_laus_SYNTHETIC_request_failed.json"),
            bls_jobs.BLS_API_V2_URL,
        )
    message = str(exc.value)
    assert "REQUEST_NOT_PROCESSED" in message
    # The message list has to survive into the exception, because BLS returns
    # HTTP 200 for this and it is the only clue about what went wrong.
    assert "Invalid Series for Series" in message
    assert "No Data Available for Series" in message


def test_laus_parser_raises_on_missing_results_block():
    body = json.dumps({"status": "REQUEST_SUCCEEDED", "message": []})
    with pytest.raises(FetchError) as exc:
        bls_jobs.parse_laus_response(body, bls_jobs.BLS_API_V2_URL)
    assert "Results.series" in str(exc.value)


def test_laus_parser_raises_on_non_json():
    with pytest.raises(FetchError):
        bls_jobs.parse_laus_response("<html>service unavailable</html>",
                                     bls_jobs.BLS_API_V2_URL)


def test_laus_cache_key_is_deterministic_and_order_independent():
    a = bls_jobs._laus_cache_key([RATE_SERIES, LF_SERIES], 2022, 2026)
    b = bls_jobs._laus_cache_key([LF_SERIES, RATE_SERIES], 2022, 2026)
    c = bls_jobs._laus_cache_key([RATE_SERIES, LF_SERIES], 2021, 2026)
    assert a == b
    assert a != c
    assert "SYNTHETIC-TEST-KEY-0000" not in a


# --------------------------------------------------------------- collect()


def test_collect_happy_path():
    cache = FakeCache(happy_responses())
    result = bls_jobs.collect(make_context(cache), make_units())

    assert set(result) == {"2608112345", "2608167890"}
    row = result["2608112345"]
    assert set(row) == {
        "county_emp_cagr_3y", "county_unemployment_rate",
        "county_employment_latest", "county_employment_year",
        "county_labor_force", "county_unemployment_year",
    }

    assert row["county_employment_latest"].value == 350000
    assert row["county_employment_year"].value == LATEST_YEAR
    assert row["county_emp_cagr_3y"].value == pytest.approx(3.0321, abs=1e-3)
    assert row["county_unemployment_rate"].value == pytest.approx(4.1)
    assert row["county_unemployment_year"].value == 2024
    assert row["county_labor_force"].value == 350123

    for key, value in row.items():
        assert not value.is_missing, key
        assert value.source, key
        assert value.vintage, key
        assert value.url, key
        # retrieved_at must come from the CachedResponse, not datetime.now().
        assert value.retrieved_at == RETRIEVED_AT, key


def test_every_value_carries_the_county_level_caveat():
    cache = FakeCache(happy_responses())
    result = bls_jobs.collect(make_context(cache), make_units())
    for geoid, row in result.items():
        for key, value in row.items():
            assert "COUNTY LEVEL FIGURE" in value.notes, f"{geoid}/{key}"
            assert "identically" in value.notes, f"{geoid}/{key}"


def test_two_submarkets_in_one_county_get_identical_but_separate_values():
    cache = FakeCache(happy_responses())
    result = bls_jobs.collect(make_context(cache), make_units())
    alpha = result["2608112345"]
    beta = result["2608167890"]
    for key in alpha:
        assert alpha[key].value == beta[key].value
        # Same figure, distinct objects, so a downstream mutation on one unit
        # cannot rewrite the other.
        assert alpha[key] is not beta[key]


def test_collect_batches_laus_into_one_post_with_a_json_body():
    cache = FakeCache(happy_responses())
    bls_jobs.collect(make_context(cache), make_units())
    posts = [c for c in cache.calls if c["method"] == "POST"]
    assert len(posts) == 1
    body = posts[0]["json_body"]
    assert body["seriesid"] == sorted([RATE_SERIES, LF_SERIES])
    assert body["annualaverage"] is True
    assert body["registrationkey"] == "SYNTHETIC-TEST-KEY-0000"
    assert body["startyear"] == "2022"
    assert body["endyear"] == "2026"
    # The registration key must never leak into the cache key or a filename.
    assert "SYNTHETIC-TEST-KEY-0000" not in posts[0]["key"]
    assert posts[0]["url"] == bls_jobs.BLS_API_V2_URL


def test_collect_makes_one_qcew_request_per_county_year_not_per_unit():
    cache = FakeCache(happy_responses())
    bls_jobs.collect(make_context(cache), make_units())
    gets = [c["url"] for c in cache.calls if c["method"] == "GET"]
    assert gets == [qcew_url(LATEST_YEAR), qcew_url(BASE_YEAR)]


def test_collect_turns_a_suppressed_county_into_missing_never_zero():
    suppressed = fixture("qcew_area_SYNTHETIC_26081_suppressed.csv")

    def serve(url: str) -> str:
        # Serve the suppressed total for every probe year. Only the year column
        # changes, so the module cannot fall through to an older unsuppressed
        # file and quietly report a zero.
        year = url.rsplit("/api/", 1)[1].split("/", 1)[0]
        return suppressed.replace('"2025"', f'"{year}"')

    responses = {qcew_url(y): serve for y in range(2019, 2027)}
    responses.update(laus_responses(fixture("bls_laus_SYNTHETIC_success.json")))
    cache = FakeCache(responses)

    row = bls_jobs.collect(make_context(cache), make_units())["2608112345"]
    for key in ("county_emp_cagr_3y", "county_employment_latest",
                "county_employment_year"):
        value = row[key]
        assert value.is_missing, key
        assert value.value is None, key
        assert value.value != 0, key
        assert "suppressed by BLS disclosure rules" in value.missing_reason, key
        assert "COUNTY LEVEL FIGURE" in value.notes, key

    # LAUS is a separate product, so it still reports.
    assert row["county_unemployment_rate"].value == pytest.approx(4.1)


def test_collect_reports_a_specific_reason_when_the_base_year_is_absent():
    responses = {
        qcew_url(LATEST_YEAR): fixture("qcew_area_SYNTHETIC_26081_2025_valid.csv"),
    }
    responses.update(laus_responses(fixture("bls_laus_SYNTHETIC_success.json")))
    cache = FakeCache(responses)

    row = bls_jobs.collect(make_context(cache), make_units())["2608112345"]
    cagr = row["county_emp_cagr_3y"]
    assert cagr.is_missing
    assert str(BASE_YEAR) in cagr.missing_reason
    assert "base year" in cagr.missing_reason
    assert "COUNTY LEVEL FIGURE" in cagr.notes
    # The level for the latest year is unaffected.
    assert row["county_employment_latest"].value == 350000


def test_collect_probes_backwards_for_the_newest_published_year():
    responses = {
        qcew_url(2023): fixture("qcew_area_SYNTHETIC_26081_2025_valid.csv").replace(
            '"2025"', '"2023"'
        ),
        qcew_url(2020): fixture("qcew_area_SYNTHETIC_26081_2022_valid.csv").replace(
            '"2022"', '"2020"'
        ),
    }
    responses.update(laus_responses(fixture("bls_laus_SYNTHETIC_success.json")))
    cache = FakeCache(responses)

    row = bls_jobs.collect(make_context(cache), make_units())["2608112345"]
    assert row["county_employment_year"].value == 2023
    assert row["county_employment_latest"].value == 350000
    assert row["county_emp_cagr_3y"].value == pytest.approx(3.0321, abs=1e-3)
    assert "2020" in row["county_emp_cagr_3y"].vintage


def test_collect_marks_laus_missing_when_the_api_reports_an_error():
    responses = {
        qcew_url(LATEST_YEAR): fixture("qcew_area_SYNTHETIC_26081_2025_valid.csv"),
        qcew_url(BASE_YEAR): fixture("qcew_area_SYNTHETIC_26081_2022_valid.csv"),
    }
    responses.update(
        laus_responses(fixture("bls_laus_SYNTHETIC_request_failed.json"))
    )
    cache = FakeCache(responses)

    row = bls_jobs.collect(make_context(cache), make_units())["2608112345"]
    for key in ("county_unemployment_rate", "county_unemployment_year",
                "county_labor_force"):
        assert row[key].is_missing, key
        assert "REQUEST_NOT_PROCESSED" in row[key].missing_reason, key
    # QCEW is unaffected by a LAUS outage.
    assert row["county_employment_latest"].value == 350000


def test_collect_returns_every_unit_even_without_a_county():
    cache = FakeCache(happy_responses())
    units = make_units() + [
        # A place GEOID with no county attached. Places can straddle county
        # lines, so there is nothing legitimate to fall back on.
        Unit(geoid="2634000", name="Orphan City", geo_type="place",
             state_fips="26"),
    ]
    result = bls_jobs.collect(make_context(cache), units)
    assert set(result) == {"2608112345", "2608167890", "2634000"}
    orphan = result["2634000"]
    assert len(orphan) == 6
    for key, value in orphan.items():
        assert value.is_missing, key
        assert "county FIPS" in value.missing_reason, key
        assert value.notes, key


def test_collect_recovers_the_county_from_a_ten_digit_geoid():
    cache = FakeCache(happy_responses())
    units = [
        Unit(geoid="2608199999", name="No County Field",
             geo_type="county_subdivision", state_fips="26"),
    ]
    row = bls_jobs.collect(make_context(cache), units)["2608199999"]
    assert row["county_employment_latest"].value == 350000


def test_without_a_key_qcew_still_loads_and_only_laus_goes_missing(monkeypatch):
    """The two sources have different requirements and must fail separately.

    QCEW is an open CSV and carries employment level and growth, which are the
    columns that move the ranking. Only LAUS needs a key. Requiring the key up
    front used to take QCEW down with it, which cost the whole jobs pillar over
    a credential that half of it does not need.
    """
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    cache = FakeCache(happy_responses())
    out = bls_jobs.collect(make_context(cache), make_units())

    for values in out.values():
        # QCEW columns are real.
        assert values["county_emp_cagr_3y"].value is not None
        assert values["county_employment_latest"].value is not None
        # LAUS columns are MISSING, and say why.
        for key in ("county_unemployment_rate", "county_labor_force"):
            assert values[key].is_missing
            assert "BLS_API_KEY" in values[key].missing_reason

    # QCEW was actually fetched; no LAUS request was attempted.
    urls = [call["url"] for call in cache.calls]
    assert any("cew" in url for url in urls)
    assert not any("timeseries" in url for url in urls)


def test_collect_propagates_a_layout_change_instead_of_guessing():
    responses = {
        qcew_url(LATEST_YEAR): fixture("qcew_area_SYNTHETIC_26081_bad_layout.csv"),
    }
    responses.update(laus_responses(fixture("bls_laus_SYNTHETIC_success.json")))
    cache = FakeCache(responses)
    with pytest.raises(FetchError) as exc:
        bls_jobs.collect(make_context(cache), make_units())
    assert "does not have the expected columns" in str(exc.value)


def test_returned_objects_are_provenance_values():
    cache = FakeCache(happy_responses())
    result = bls_jobs.collect(make_context(cache), make_units())
    for row in result.values():
        for value in row.values():
            assert isinstance(value, Value)
