"""Interactive setup for the three free API keys.

Run this instead of editing .env by hand:

    Windows    .venv\\Scripts\\python setup_keys.py
    Mac/Linux  .venv/bin/python setup_keys.py

It asks for each key one at a time, checks the shape of what you paste,
strips stray whitespace and line breaks, and writes .env correctly. Pasting a
long token into a shell is where this goes wrong, so nothing here is typed at
a command prompt.

Press Enter on any key to skip it. A skipped key is not an error: the columns
it would have filled come through as MISSING, with the reason attached.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

KEYS = [
    {
        "name": "CENSUS_API_KEY",
        "label": "Census ACS",
        "why": "population, household growth, renter share, income, age profile",
        "impact": "Without this the whole demand pillar is MISSING. This is the one that matters.",
        "url": "https://api.census.gov/data/key_signup.html",
        "shape": re.compile(r"^[0-9a-fA-F]{20,60}$"),
        "shape_note": "a long string of hex characters, no dashes",
    },
    {
        "name": "BLS_API_KEY",
        "label": "BLS LAUS",
        "why": "county unemployment rate and labour force",
        "impact": "Without this the unemployment column is MISSING. Employment growth still works, it uses a different BLS file that needs no key.",
        "url": "https://data.bls.gov/registrationEngine/",
        "shape": re.compile(r"^[0-9a-fA-F]{20,60}$"),
        "shape_note": "a long string of hex characters, no dashes",
    },
    {
        "name": "HUD_API_KEY",
        "label": "HUD Fair Market Rents",
        "why": "the independent rent cross-check",
        "impact": "Without this the rent columns are MISSING, including Zillow, because the module checks its key before doing any work.",
        "url": "https://www.huduser.gov/portal/dataset/fmr-api.html",
        "shape": re.compile(r"^eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$"),
        "shape_note": "a very long token starting with eyJ and containing exactly two full stops",
    },
]

PLACEHOLDER_HINTS = ("...", "…", "<", ">", "paste", "your key")


def read_existing() -> dict[str, str]:
    found: dict[str, str] = {}
    if not ENV_PATH.exists():
        return found
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        value = value.strip()
        if value:
            found[name.strip()] = value
    return found


def mask(value: str) -> str:
    if len(value) <= 12:
        return value[:3] + "..." + value[-2:]
    return f"{value[:6]}...{value[-4:]} ({len(value)} characters)"


def clean(raw: str) -> str:
    # Strip quotes people add, any whitespace a wrapped paste introduced, and a
    # Bearer prefix somebody copied along with the HUD token.
    text = "".join(raw.split())
    text = text.strip().strip('"').strip("'")
    if text.lower().startswith("bearer"):
        text = text[6:].strip()
    return text


def looks_like_placeholder(value: str) -> str:
    lowered = value.lower()
    for hint in PLACEHOLDER_HINTS:
        if hint in lowered:
            return (
                f"that contains '{hint}', which looks like example text rather "
                f"than a real key"
            )
    return ""


def ask(spec: dict, existing: str) -> str:
    print()
    print("=" * 72)
    print(f"  {spec['name']}  ({spec['label']})")
    print(f"  Used for: {spec['why']}")
    print(f"  Get one:  {spec['url']}")
    print(f"  {spec['impact']}")
    if existing:
        print(f"  Currently set to: {mask(existing)}")
        print("  Press Enter to keep it, or paste a new one to replace it.")
    else:
        print("  Press Enter to skip.")
    print("=" * 72)

    while True:
        try:
            raw = input(f"{spec['name']}= ")
        except (EOFError, KeyboardInterrupt):
            print("\nStopped. Nothing was written.")
            sys.exit(1)

        value = clean(raw)
        if not value:
            return existing

        problem = looks_like_placeholder(value)
        if problem:
            print(f"  That does not look right: {problem}. Try again.")
            continue

        if not spec["shape"].match(value):
            print(f"  Warning: expected {spec['shape_note']}.")
            print(f"  You gave {len(value)} characters starting '{value[:12]}'.")
            try:
                answer = input("  Use it anyway? (y/N) ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nStopped. Nothing was written.")
                sys.exit(1)
            if answer != "y":
                continue
        return value


def write(values: dict[str, str]) -> None:
    lines = [
        "# Written by setup_keys.py. This file is gitignored and must never be",
        "# committed. Rerun setup_keys.py to change a key.",
        "",
    ]
    for spec in KEYS:
        value = values.get(spec["name"], "")
        lines.append(f"# {spec['label']}: {spec['why']}")
        lines.append(f"# {spec['url']}")
        lines.append(f"{spec['name']}={value}")
        lines.append("")
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print()
    print("Submarket screener: API key setup")
    print(f"Writing to {ENV_PATH}")

    existing = read_existing()
    values: dict[str, str] = {}
    for spec in KEYS:
        values[spec["name"]] = ask(spec, existing.get(spec["name"], ""))

    write(values)

    print()
    print("-" * 72)
    print(f"Saved {ENV_PATH}")
    missing = []
    for spec in KEYS:
        value = values.get(spec["name"], "")
        if value:
            print(f"  set      {spec['name']:<16} {mask(value)}")
        else:
            print(f"  NOT SET  {spec['name']:<16} {spec['label']}")
            missing.append(spec)

    if missing:
        print()
        print("Skipped keys are fine. Their columns will read MISSING with a reason,")
        print("rather than being guessed at. Rerun this script to add them later.")

    print()
    print("Next:")
    exe = "\\.venv\\Scripts\\python" if sys.platform == "win32" else ".venv/bin/python"
    print(f"  {exe.lstrip(chr(92))} -m screener.cli check")
    print(f"  {exe.lstrip(chr(92))} -m screener.cli run --market madison_wi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
