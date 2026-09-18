"""The Census API answers a bad key with HTTP 200 and an HTML page.

A parser that only checks "is this JSON" reports that no ACS vintage answered,
which sends you hunting for a data problem that does not exist. These pin the
message to the actual cause.
"""
from __future__ import annotations

from screener.sources import census_acs

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
    """A "Missing Key" page no longer means somebody forgot to set the key.

    The screen deliberately runs keyless, so this page means the keyless
    allowance ran out. On a CI runner the IP address is shared, so the requests
    that used it up may not even be ours. Blaming an unset key would send the
    reader to fix something that is not broken.
    """
    msg = census_acs._explain_non_json(2024, "probe", MISSING)
    assert "daily quota" in msg
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
