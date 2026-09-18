"""The Census API answers a bad key with HTTP 200 and an HTML page.

A parser that only checks "is this JSON" reports that no ACS vintage answered,
which sends you hunting for a data problem that does not exist. These pin the
message to the actual cause.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from screener.cache import FetchError
from screener.sources import census_acs, census_acs_sf

INVALID = (
    '<html style="font-size: 14px;">\n<head>\n    <title>Invalid Key</title>\n'
    '    <link rel="icon" type="image/x-icon" href="favicon.ico">\n</head>'
)
MISSING = (
    '<html style="font-size: 14px;">\n<head>\n    <title>Missing Key</title>\n'
    "</head>"
)


def test_invalid_key_is_named_as_a_key_problem():
    msg = census_acs._explain_non_json(2024, "acs_probe_2024_55", INVALID)
    assert "rejected the key" in msg
    assert "activation link" in msg
    assert "setup_keys.py" in msg
    # It must not blame the vintage, which is what the old message did.
    assert "Nothing is wrong with the ACS vintage" in msg


def test_missing_key_is_distinguished_from_an_invalid_one():
    """"Missing Key" means no key arrived, which is now always fatal.

    Census made a key mandatory on every Data API request on 12 May 2026. The
    message has to say that, because the obvious reading of a failure that
    repeats across every vintage is that the data is unavailable, and somebody
    would go looking for a release that is sitting there waiting for a key.
    """
    msg = census_acs._explain_non_json(2024, "probe", MISSING)
    assert "12 May 2026" in msg
    assert "retrying other years will not help" in msg
    assert "key_signup" in msg
    assert "rejected the key" not in msg


def test_an_unexpected_html_page_still_reports_its_title():
    page = "<html><head><title>Service Unavailable</title></head></html>"
    msg = census_acs._explain_non_json(2023, "probe", page)
    assert "Service Unavailable" in msg
    assert "HTML page instead of JSON" in msg


def test_a_plain_non_json_body_falls_through_to_the_raw_text():
    msg = census_acs._explain_non_json(2023, "probe", "error: something odd")
    assert "non-JSON body" in msg
    assert "something odd" in msg


def test_the_key_parameter_is_omitted_entirely_when_there_is_no_key():
    """Census must not be sent an empty key, it must be sent no key at all.

    "key=" with nothing after it is not the same request as no key parameter.
    The API treats the empty one as a supplied credential and rejects it, which
    would put the whole demand pillar back behind a credential that the data
    does not actually need.
    """
    sent = {}

    class FakeCache:
        def get(self, url, *, key, params, ttl_days):
            sent.update(params)
            raise AssertionError("stop here, the params are what is under test")

    class FakeCtx:
        cache = FakeCache()

    for supplied, expected in (("", None), ("abc123", "abc123")):
        sent.clear()
        try:
            census_acs._query(FakeCtx(), 2024, ["B01003_001E"],
                              {"for": "state:55"}, supplied, "probe")
        except AssertionError as exc:
            if "stop here" not in str(exc):
                raise
        assert sent.get("key") == expected, f"with key={supplied!r}"
        if expected is None:
            assert "key" not in sent


def test_without_a_key_it_reads_the_summary_files_and_never_calls_the_api(monkeypatch):
    """No key is no longer a dead end, and must not become a wasted API call.

    The Data API has required a key on every request since 12 May 2026, so
    calling it without one can only produce a Missing Key page. The summary
    files carry the same release and need no key, so that is where a keyless
    run goes.
    """
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    api_calls = []
    monkeypatch.setattr(census_acs, "find_latest_vintage",
                        lambda *a, **k: api_calls.append(a) or 2024)
    monkeypatch.setattr(census_acs, "fetch_api_maps",
                        lambda *a, **k: api_calls.append(a) or None)

    sentinel = census_acs.AcsMaps(
        latest={}, prior={}, latest_year=2024, prior_year=2019,
        latest_url="u", prior_url="p", retrieved_latest="", retrieved_prior="",
        prior_error="", source_name="summary file",
    )
    monkeypatch.setattr(census_acs_sf, "fetch_maps", lambda ctx, units: sentinel)

    logged = []
    ctx = SimpleNamespace(log=logged.append)
    census_acs.collect(ctx, [])

    assert not api_calls, "it called the Data API despite having no key"
    assert any("summary file" in line for line in logged), logged


def test_with_a_key_it_uses_the_api_and_never_downloads_the_summary_files(monkeypatch):
    """The API is a few kilobytes against a few hundred megabytes. Prefer it."""
    monkeypatch.setenv("CENSUS_API_KEY", "abc123")
    sentinel = census_acs.AcsMaps(
        latest={}, prior={}, latest_year=2024, prior_year=2019,
        latest_url="u", prior_url="p", retrieved_latest="", retrieved_prior="",
        prior_error="", source_name="api",
    )
    monkeypatch.setattr(census_acs, "fetch_api_maps", lambda ctx, key: sentinel)

    def explode(*a, **k):
        raise AssertionError("downloaded the summary files despite having a key")

    monkeypatch.setattr(census_acs_sf, "fetch_maps", explode)
    census_acs.collect(SimpleNamespace(log=lambda _: None), [])


def test_both_routes_run_the_same_arithmetic(monkeypatch):
    """The two routes must not be able to disagree about a figure.

    Same underlying release, so the same GEOID must produce the same renter
    share whichever route filled the maps. The file spelling (B25003_E003)
    differs from the API spelling (B25003_003E), and that translation is the
    one place a divergence could hide.
    """
    from screener.sources.census_acs_sf import _api_name

    api_row = {"B25003_001E": "1000", "B25003_003E": "450", "B01003_001E": "2600"}
    file_row = {_api_name(k): v for k, v in
                {"B25003_E001": "1000", "B25003_E003": "450", "B01003_E001": "2600"}.items()}
    assert file_row == api_row

    unit = SimpleNamespace(geoid="5500100275", name="Somewhere")
    results = []
    for source in ("api", "summary file"):
        maps = census_acs.AcsMaps(
            latest={"5500100275": api_row}, prior={},
            latest_year=2024, prior_year=2019,
            latest_url="u", prior_url="p",
            retrieved_latest="2026-01-01T00:00:00Z", retrieved_prior="",
            prior_error="", source_name=source,
        )
        results.append(census_acs.compute_metrics([unit], maps))

    left, right = results
    assert left["5500100275"]["renter_share"].value == 45.0
    assert (left["5500100275"]["renter_share"].value
            == right["5500100275"]["renter_share"].value)
