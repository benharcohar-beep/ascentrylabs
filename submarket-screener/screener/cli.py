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

# No key is required to run the screen. Each one either raises a rate limit or
# adds a few columns, and the tool says which columns went MISSING and why. The
# fourth field is what you actually lose without it.
KEY_STATUS = [
    ("CENSUS_API_KEY", "Census ACS", "https://api.census.gov/data/key_signup.html",
     "no columns. The Data API has needed a key since 12 May 2026, so without "
     "one the same figures are read from the summary files instead: same "
     "release, much larger download. A key only makes the pull lighter."),
    ("BLS_API_KEY", "BLS LAUS", "https://data.bls.gov/registrationEngine/",
     "the county unemployment columns. QCEW employment needs no key."),
    ("HUD_API_KEY", "HUD Fair Market Rents",
     "https://www.huduser.gov/portal/dataset/fmr-api.html",
     "the FMR cross-check columns. Zillow rents need no key."),
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

    print("\nAPI keys (all free, none required):")
    absent = []
    for env, label, url, cost in KEY_STATUS:
        present = bool(os.environ.get(env, "").strip())
        if not present:
            absent.append((env, cost))
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

    if absent:
        print("\nThe screen runs without these. What each one is costing you:")
        for env, cost in absent:
            print(f"  {env}: {cost}")
        print("Add any of them to submarket-screener/.env and rerun.")
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


def cmd_coverage(args) -> int:
    """Print, per column, how many submarkets actually got a figure.

    The run already reports one coverage percentage per submarket, which tells
    you that something is missing but not what. This lists every scored column
    against the number of submarkets holding a real value for it, and groups
    the missing ones by the reason recorded at the time. That turns "27%
    coverage" into a list of specific things to go and fix.
    """
    weights = load_weights()
    failed = 0
    for key in _targets(args):
        try:
            bundle = assemble.load(key, OUTPUT_DIR)
        except FileNotFoundError as exc:
            print(f"  {exc}", file=sys.stderr)
            failed += 1
            continue

        units = bundle["units"]
        values = bundle["values"]
        specs = bundle["specs"]
        total = len(units)
        print(f"\n{bundle['market']['name']}: column coverage across {total} submarkets")
        print(f"  shortlist rule: {bundle.get('shortlist_method', 'unknown')}")

        by_pillar: dict[str, list[str]] = {}
        for name, spec in specs.items():
            by_pillar.setdefault(spec.get("pillar") or "unassigned", []).append(name)

        for pillar in list(weights.pillars) + [
            p for p in sorted(by_pillar) if p not in weights.pillars
        ]:
            names = by_pillar.get(pillar)
            if not names:
                continue
            print(f"\n  [{pillar}] weight {weights.pillars.get(pillar, 0)}")
            for name in sorted(names):
                spec = specs[name]
                reasons: dict[str, int] = {}
                present = 0
                for unit in units:
                    cell = values.get(unit["geoid"], {}).get(name)
                    if cell is not None and cell.get("value") is not None:
                        present += 1
                    else:
                        reason = (cell or {}).get("missing_reason") or "no cell was produced"
                        reasons[reason.strip().splitlines()[0][:110]] = (
                            reasons.get(reason.strip().splitlines()[0][:110], 0) + 1
                        )
                mark = "ok  " if present == total else ("PART" if present else "NONE")
                scored = "" if spec.get("scored", True) else "  (not scored)"
                weight = weights.metrics.get(name)
                weight_txt = f" w={weight}" if weight is not None else ""
                print(f"    {mark} {name:<34}{weight_txt:<7} {present}/{total}{scored}")
                for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
                    print(f"         {count:>3} missing: {reason}")

        blocked = bundle.get("failures") or {}
        if blocked:
            print("\n  sources that returned nothing at all:")
            for source, message in blocked.items():
                print(f"    {source}: {str(message).strip().splitlines()[0][:150]}")
    return 1 if failed else 0


def cmd_verify(args) -> int:
    """Recalculate the workbook's live formulas and compare against Python.

    The scoring tab holds real Excel formulas so an interviewer can click a
    cell and see the arithmetic. That is only worth anything if the formulas
    agree with the Python scorer. They have disagreed before: N(range) returns
    #VALUE! over a range, which blanked every pillar score and the whole
    ranking tab while the Python output looked perfect.

    The test suite checks this against fixtures. This checks it against the
    workbook actually produced from real data, where the awkward shapes live:
    columns that are entirely missing, single valued columns, thin rows.
    """
    try:
        import formulas  # noqa: PLC0415
    except ImportError:
        print("The 'formulas' package is not installed, so the workbook "
              "formulas cannot be independently recalculated. Install it with: "
              "pip install formulas", file=sys.stderr)
        return 2

    weights = load_weights()
    problems = 0
    for key in _targets(args):
        try:
            bundle = assemble.load(key, OUTPUT_DIR)
        except FileNotFoundError as exc:
            print(f"  {exc}", file=sys.stderr)
            problems += 1
            continue

        ranked = score.score_market(bundle, weights)
        path = OUTPUT_DIR / key / f"{key}_submarket_screen.xlsx"
        if not path.exists():
            print(f"  no workbook at {path}. Run report first.", file=sys.stderr)
            problems += 1
            continue

        print(f"\n{bundle['market']['name']}: recalculating {path.name} with an "
              f"independent engine")
        model = formulas.ExcelModel().loads(str(path)).finish()
        cells = {k.upper(): v for k, v in model.calculate().items()}
        sheet = f"'[{path.name.upper()}]RANKING'!"

        def cell(ref):
            value = cells.get(sheet + ref)
            try:
                return value.value[0, 0]
            except (AttributeError, IndexError, TypeError):
                return value

        mismatches = 0
        for i, result in enumerate(ranked):
            row = 6 + i                      # the ranking table starts on row 6
            name = str(cell(f"B{row}")).strip()
            if name != result.name:
                print(f"    MISMATCH row {row}: workbook {name!r}, Python "
                      f"{result.name!r}")
                mismatches += 1
                continue
            try:
                total = float(cell(f"C{row}"))
            except (TypeError, ValueError):
                total = None
            expected = result.total
            if expected is None:
                continue
            if total is None or abs(total - expected) > 0.05:
                print(f"    MISMATCH {result.name}: workbook total {total!r}, "
                      f"Python {expected:.2f}")
                mismatches += 1
        if mismatches:
            print(f"  {mismatches} cells disagree. The workbook would contradict "
                  f"the one pager in front of an interviewer.")
            problems += 1
        else:
            print(f"  every one of the {len(ranked)} ranking rows agrees with the "
                  f"Python scorer, name and total.")
    return 1 if problems else 0


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
    add_common(sub.add_parser(
        "coverage", help="per column, how many submarkets got a figure and why not"))
    add_common(sub.add_parser(
        "verify", help="recalculate the workbook formulas and compare with Python"))
    add_common(sub.add_parser("run", help="fetch then report"), network=True)

    args = parser.parse_args(argv)
    return {
        "check": cmd_check, "fetch": cmd_fetch,
        "report": cmd_report, "run": cmd_run,
        "coverage": cmd_coverage, "verify": cmd_verify,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
