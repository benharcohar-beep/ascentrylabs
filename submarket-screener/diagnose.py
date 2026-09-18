"""Work out why a source failed, with enough detail to fix it.

Run:  .venv\\Scripts\\python diagnose.py        (Windows)
      .venv/bin/python diagnose.py             (Mac/Linux)

Prints a compact report: which keys are loaded, what the Census API actually
says when called, and the real layout of any cached file whose parser is
failing. Nothing here is guessed at; it reports exactly what came back.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv                      # noqa: E402
import os                                           # noqa: E402
import requests                                     # noqa: E402

load_dotenv(ROOT / ".env")

LINE = "=" * 70


def section(title: str) -> None:
    print()
    print(LINE)
    print(title)
    print(LINE)


def show_keys() -> None:
    """Report whether each key is present, without exposing it.

    On a public repository, GitHub Actions logs are world readable. GitHub
    masks the exact secret value, but it does not mask a fragment of it, so
    printing the first six characters of a key would publish them. In CI we
    print the length and nothing else. The length alone is enough to catch the
    usual mistakes: a truncated paste, or a JWT that lost its tail.
    """
    section("1. KEYS")
    in_ci = bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"))
    for name in ("CENSUS_API_KEY", "BLS_API_KEY", "HUD_API_KEY"):
        value = os.environ.get(name, "")
        if not value:
            print(f"  {name:<16} NOT SET")
        elif in_ci:
            print(f"  {name:<16} set, {len(value)} characters "
                  f"(value hidden: this log may be public)")
        else:
            print(f"  {name:<16} {len(value)} chars, "
                  f"starts '{value[:6]}', ends '{value[-4:]}'")


def probe_census() -> None:
    section("2. CENSUS ACS API")
    key = os.environ.get("CENSUS_API_KEY", "")
    base = "https://api.census.gov/data"

    for year in (2024, 2023, 2022):
        for label, params in (
            ("with key", {"get": "NAME,B01003_001E", "for": "state:55", "key": key}),
            ("no key  ", {"get": "NAME,B01003_001E", "for": "state:55"}),
        ):
            if label.strip() == "with key" and not key:
                continue
            url = f"{base}/{year}/acs/acs5"
            try:
                resp = requests.get(url, params=params, timeout=45)
            except requests.RequestException as exc:
                print(f"  {year} {label}: NETWORK ERROR {type(exc).__name__}: {exc}")
                continue
            body = resp.text.strip().replace("\n", " ")[:220]
            print(f"  {year} {label}: HTTP {resp.status_code}  {body}")
        print()


def probe_census_geography() -> None:
    section("3. CENSUS ACS, THE ACTUAL GEOGRAPHY QUERY THE TOOL MAKES")
    key = os.environ.get("CENSUS_API_KEY", "")
    if not key:
        print("  skipped, no key")
        return
    url = "https://api.census.gov/data/2023/acs/acs5"
    attempts = {
        "repeated in params": [
            ("get", "NAME,B01003_001E"), ("for", "county subdivision:*"),
            ("in", "state:55"), ("in", "county:025"), ("key", key),
        ],
        "single in param  ": [
            ("get", "NAME,B01003_001E"), ("for", "county subdivision:*"),
            ("in", "state:55 county:025"), ("key", key),
        ],
    }
    for label, params in attempts.items():
        try:
            resp = requests.get(url, params=params, timeout=45)
        except requests.RequestException as exc:
            print(f"  {label}: NETWORK ERROR {exc}")
            continue
        body = resp.text.strip().replace("\n", " ")[:200]
        print(f"  {label}: HTTP {resp.status_code}  {body}")
        print(f"     sent: {resp.url.split('&key=')[0]}")
        print()


def dump_cached(fragment: str, title: str, lines: int = 6) -> None:
    section(title)
    cache = ROOT / "data" / "cache"
    if not cache.exists():
        print("  no cache directory")
        return
    hits = []
    for meta_path in cache.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if fragment in meta.get("url", ""):
            hits.append((meta, meta_path.with_suffix("").with_suffix(".bin")))
    if not hits:
        print(f"  nothing cached matching '{fragment}'")
        return
    for meta, body_path in hits[:2]:
        print(f"  url:   {meta.get('url')}")
        print(f"  bytes: {meta.get('bytes')}   retrieved: {meta.get('retrieved_at')}")
        if not body_path.exists():
            print("  body file missing")
            continue
        text = body_path.read_bytes().decode("latin-1", errors="replace")
        for i, row in enumerate(text.splitlines()[:lines]):
            fields = next(csv.reader([row])) if row.strip() else []
            print(f"  line {i}: {len(fields)} fields")
            print(f"    {row[:300]}")
        print()


def probe_hud() -> None:
    section("6. HUD FAIR MARKET RENTS, RAW RESPONSE")
    token = os.environ.get("HUD_API_KEY", "")
    if not token:
        print("  skipped, no key")
        return
    # Dane County, Wisconsin. The county entity id is the 5 digit FIPS plus
    # 99999, which is the assumption that needs confirming.
    entity = "5502599999"
    headers = {"Authorization": f"Bearer {token}"}
    for year in (2026, 2025):
        url = f"https://www.huduser.gov/hudapi/public/fmr/data/{entity}"
        try:
            resp = requests.get(url, params={"year": year}, headers=headers, timeout=45)
        except requests.RequestException as exc:
            print(f"  FY{year}: NETWORK ERROR {type(exc).__name__}: {exc}")
            continue
        print(f"  FY{year}: HTTP {resp.status_code}")
        body = resp.text.strip()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            print(f"    non-JSON: {body[:300]}")
            continue
        # Print the shape, not the whole payload, so the report stays readable.
        print(f"    top level keys: {list(parsed)[:10]}")
        data = parsed.get("data")
        if isinstance(data, dict):
            print(f"    data keys: {list(data)[:12]}")
            basic = data.get("basicdata")
            print(f"    basicdata type: {type(basic).__name__}")
            if isinstance(basic, dict):
                print(f"    basicdata keys: {list(basic)[:12]}")
            elif isinstance(basic, list) and basic:
                print(f"    basicdata[0] keys: {list(basic[0])[:12]}")
                print(f"    basicdata[0]: {json.dumps(basic[0])[:250]}")
        else:
            print(f"    data is {type(data).__name__}: {json.dumps(data)[:250]}")
        print()


def main() -> int:
    print("Submarket screener diagnostic")
    print(f"Python {sys.version.split()[0]}  requests {requests.__version__}")
    show_keys()
    probe_census()
    probe_census_geography()
    dump_cached("econ/bps/Place", "4. CACHED BPS PLACE FILE, REAL LAYOUT", lines=6)
    dump_cached("econ/bps/County", "5. CACHED BPS COUNTY FILE, REAL LAYOUT", lines=6)
    probe_hud()
    print()
    print("Send this whole output back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
