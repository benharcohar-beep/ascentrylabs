"""Command line entry point.

  python -m screener.cli check
  python -m screener.cli fetch  --market madison_wi
  python -m screener.cli report --market madison_wi
  python -m screener.cli run    --market madison_wi      (fetch then report)
  python -m screener.cli run    --all

fetch is the only command that touches the network. report and the Streamlit
app read output/<market>/raw.json, so once fetch has run once the demo works
with the wifi off.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import assemble, excel, onepager, score
from .cache import Cache, FetchError
from .config import CACHE_DIR, OUTPUT_DIR, list_markets, load_market, load_weights
from .context import Context
from .metrics import validate_weights

KEY_STATUS = [
    ("CENSUS_API_KEY", "Census ACS", "https://api.census.gov/data/key_signup.html"),
    ("BLS_API_KEY", "BLS LAUS", "https://data.bls.gov/registrationEngine/"),
    ("HUD_API_KEY", "HUD Fair Market Rents", "https://www.huduser.gov/portal/dataset/fmr-api.html"),
]


def _context(args, market_key: str) -> Context:
    weights = load_weights()
    return Context(
        cache=Cache(CACHE_DIR, refresh=getattr(args, "refresh", False),
                    offline=getattr(args, "offline", False)),
        market=load_market(market_key),
        weights=weights,
        output_dir=OUTPUT_DIR,
        use_osrm=getattr(args, "osrm", False),
        verbose=not getattr(args, "quiet", False),
    )


def cmd_check(args) -> int:
    print("Markets configured:")
    for key in list_markets():
        market = load_market(key)
        print(f"  {key:<18} {market.name:<28} "
              f"{len(market.counties)} counties, {market.geo_type.replace('_', ' ')}")

    print("\nAPI keys (all free):")
    missing_any = False
    for env, label, url in KEY_STATUS:
        present = bool(os.environ.get(env, "").strip())
        if not present:
            missing_any = True
        print(f"  [{'x' if present else ' '}] {env:<16} {label:<24} {url}")

    print("\nWeights:")
    weights = load_weights()
    problems = validate_weights(weights)
    for pillar, value in weights.pillars.items():
        print(f"  {pillar:<12} {value}")
    print(f"  method: {weights.scoring_method}")
    if problems:
        print("\nProblems in config/weights.yml:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nweights.yml is consistent with the metrics the source modules produce.")

    if missing_any:
        print("\nAt least one key is missing. Add them to submarket-screener/.env "
              "and rerun. fetch will stop with instructions if it needs one it "
              "does not have.")
        return 2
    return 0


def cmd_fetch(args) -> int:
    failed = 0
    for key in _targets(args):
        ctx = _context(args, key)
        try:
            bundle = assemble.build(ctx)
        except FetchError as exc:
            print(f"\nFETCH FAILED for {key}:\n  {exc}\n", file=sys.stderr)
            failed += 1
            continue
        path = assemble.save(bundle, OUTPUT_DIR)
        print(f"  saved {path}")
        if bundle["failures"]:
            print("  sources that did not return data:")
            for name, msg in bundle["failures"].items():
                print(f"    {name}: {msg.splitlines()[0][:160]}")
    return 1 if failed else 0


def cmd_report(args) -> int:
    weights = load_weights()
    failed = 0
    for key in _targets(args):
        try:
            bundle = assemble.load(key, OUTPUT_DIR)
        except FileNotFoundError as exc:
            print(f"  {exc}", file=sys.stderr)
            failed += 1
            continue
        ranked = score.score_market(bundle, weights)
        explanation = score.explain(bundle, ranked)

        market_dir = OUTPUT_DIR / key
        xlsx = excel.build_workbook(bundle, weights, explanation,
                                    market_dir / f"{key}_submarket_screen.xlsx")
        html_path = onepager.render(bundle, ranked, explanation, weights,
                                    market_dir / f"{key}_one_pager.html")
        print(f"\n{bundle['market']['name']}")
        print(f"  workbook  {xlsx}")
        print(f"  one pager {html_path}")
        print("  top 3:")
        for r in ranked[:3]:
            print(f"    {r.rank}. {r.name:<30} {r.total if r.total is not None else 'n/a':>6} "
                  f"  coverage {r.coverage * 100:.0f}%")
        print("  why:")
        for line in explanation:
            print(f"    - {line}")
    return 1 if failed else 0


def cmd_run(args) -> int:
    rc = cmd_fetch(args)
    rc2 = cmd_report(args)
    return rc or rc2


def _targets(args) -> list[str]:
    if getattr(args, "all", False):
        return list_markets()
    if not args.market:
        raise SystemExit("Pass --market <key> or --all. Keys: " + ", ".join(list_markets()))
    return [args.market]


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    parser = argparse.ArgumentParser(prog="screener", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p, network: bool = False):
        p.add_argument("--market", help="market key, see 'check'")
        p.add_argument("--all", action="store_true", help="every configured market")
        p.add_argument("--quiet", action="store_true")
        if network:
            p.add_argument("--refresh", action="store_true",
                           help="ignore the cache and download everything again")
            p.add_argument("--offline", action="store_true",
                           help="fail rather than download; use only what is cached")
            p.add_argument("--osrm", action="store_true",
                           help="also look up drive distance from the public OSRM demo server")

    sub.add_parser("check", help="show markets, keys and weight consistency")
    add_common(sub.add_parser("fetch", help="download and cache the data"), network=True)
    add_common(sub.add_parser("report", help="build the workbook and one pager"))
    add_common(sub.add_parser("run", help="fetch then report"), network=True)

    args = parser.parse_args(argv)
    return {
        "check": cmd_check, "fetch": cmd_fetch,
        "report": cmd_report, "run": cmd_run,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
