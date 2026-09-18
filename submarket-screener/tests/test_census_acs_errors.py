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
    msg = census_acs._explain_non_json(2024, "probe", MISSING)
    assert "no key reached the API" in msg
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
