"""Build the raw data table for one market.

Order of operations, and why:

  1. Gazetteer gives the full universe of municipalities in the trade area,
     with a centroid for each.
  2. Straight-line distance to the nearest employment centre is computed for
     the whole universe, offline, and anything beyond max_distance_miles drops
     out. This is the trade area filter.
  3. ACS is pulled for everything left. The ACS call is a county or state
     wildcard, so pulling it for fifty municipalities costs the same as
     pulling it for ten.
  4. The shortlist is the target_submarkets largest survivors by population,
     above min_population, plus anything in always_include.
  5. The remaining sources (rents, permits, jobs, schools, municipal attitude)
     run on the shortlist only.

Everything is written to output/<market>/raw.json so that scoring, the
workbook, the one-pagers and the Streamlit app all read the same frozen
snapshot and none of them touch the network.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .cache import FetchError, MissingCredential
from .context import Context
from .metrics import registry
from .provenance import Unit, Value, missing
from .sources import census_gazetteer, census_relationship, geo


def _unit_to_dict(unit: Unit) -> dict:
    return {
        "geoid": unit.geoid,
        "name": unit.name,
        "geo_type": unit.geo_type,
        "state_fips": unit.state_fips,
        "county_fips": unit.county_fips,
        "county_name": unit.county_name,
        "lat": unit.lat,
        "lon": unit.lon,
        "land_area_sqmi": unit.land_area_sqmi,
        "zctas": unit.zctas,
    }


def _merge(target: dict[str, dict[str, Value]], new: dict[str, dict[str, Value]]) -> None:
    for geoid, values in new.items():
        target.setdefault(geoid, {}).update(values)


def _run_source(ctx: Context, name: str, fn, units, failures: dict, **kwargs
                ) -> dict[str, dict[str, Value]]:
    """Call one source module, turning any failure into MISSING cells."""
    try:
        return fn(ctx, units, **kwargs)
    except MissingCredential as exc:
        ctx.log(f"SKIPPED {name}: {exc}")
        failures[name] = str(exc)
    except FetchError as exc:
        ctx.log(f"FAILED  {name}: {exc}")
        failures[name] = str(exc)
    except Exception as exc:  # noqa: BLE001 - a source must never kill the run
        ctx.log(f"ERROR   {name}: {type(exc).__name__}: {exc}")
        failures[name] = f"{type(exc).__name__}: {exc}"
    return {}


def build(ctx: Context) -> dict:
    market = ctx.market
    ctx.log(f"=== {market.name} ===")
    failures: dict[str, str] = {}
    provenance: dict[str, dict] = {}

    # ---------------------------------------------------------------- 1. universe
    universe, gaz_prov = census_gazetteer.build_universe(ctx)
    provenance["gazetteer"] = gaz_prov
    if not universe:
        raise FetchError(
            f"No municipalities found for {market.name}. Check the county FIPS "
            f"codes and geo_type in config/markets/{market.key}.yml"
        )

    # ------------------------------------------------- 2. trade area distance filter
    distances = geo.collect(ctx, universe)
    in_range = []
    for unit in universe:
        d = distances.get(unit.geoid, {}).get("miles_to_employment")
        if d is not None and not d.is_missing and d.value <= market.max_distance_miles:
            in_range.append(unit)
    ctx.log(
        f"Within {market.max_distance_miles:.0f} miles of an employment centre: "
        f"{len(in_range)} of {len(universe)}"
    )

    # ------------------------------------------------------------------- 3. ACS
    from .sources import census_acs

    acs_values = _run_source(ctx, "census_acs", census_acs.collect, in_range, failures)

    # -------------------------------------------------------------- 4. shortlist
    def population_of(unit: Unit) -> float:
        v = acs_values.get(unit.geoid, {}).get("population")
        return float(v.value) if v is not None and not v.is_missing else -1.0

    forced = set(market.always_include)
    excluded = set(market.always_exclude)

    eligible = [
        u for u in in_range
        if u.geoid not in excluded
        and (population_of(u) >= market.min_population or u.geoid in forced)
    ]
    eligible.sort(key=population_of, reverse=True)

    shortlist = [u for u in eligible if u.geoid in forced]
    for unit in eligible:
        if len(shortlist) >= market.target_submarkets:
            break
        if unit.geoid not in forced:
            shortlist.append(unit)
    shortlist.sort(key=population_of, reverse=True)

    shortlist_method = (
        f"largest {market.target_submarkets} municipalities by ACS population, "
        f"above {market.min_population:,}, within "
        f"{market.max_distance_miles:.0f} miles of an employment centre"
    )

    if not acs_values:
        # The population rule cannot run without ACS. The fallback still honours
        # always_include and always_exclude, because silently screening an
        # excluded municipality is worse than screening nothing, and it is
        # recorded in the bundle so the outputs can say the rule changed.
        ctx.log(
            "WARNING: ACS returned nothing, so the shortlist could not be ranked "
            "by population. Falling back to the closest municipalities by "
            "distance. The population floor cannot be applied."
        )
        shortlist_method = (
            f"FALLBACK, ACS unavailable: closest {market.target_submarkets} "
            f"municipalities by straight-line distance. The population floor "
            f"was NOT applied."
        )
        candidates = [u for u in in_range if u.geoid not in excluded]
        forced_units = [u for u in candidates if u.geoid in forced]
        rest = sorted(
            (u for u in candidates if u.geoid not in forced),
            key=lambda u: distances[u.geoid]["miles_to_employment"].value,
        )
        shortlist = (forced_units + rest)[: max(market.target_submarkets, len(forced_units))]

    unreachable_forced = sorted(forced - {u.geoid for u in in_range})
    if unreachable_forced:
        ctx.log(
            "WARNING: always_include GEOIDs outside the trade area filter, so "
            "they were not screened: " + ", ".join(unreachable_forced)
        )

    ctx.log(f"Shortlist: {len(shortlist)} submarkets")
    for unit in shortlist:
        pop = population_of(unit)
        ctx.log(f"   {unit.name:<34} pop {pop:>9,.0f}" if pop > 0 else f"   {unit.name}")

    # --------------------------------------------------- 5. crosswalk and sources
    provenance["zcta_crosswalk"] = census_relationship.attach_zctas(ctx, shortlist)

    values: dict[str, dict[str, Value]] = {}
    _merge(values, {g: v for g, v in acs_values.items() if g in {u.geoid for u in shortlist}})
    _merge(values, geo.collect(ctx, shortlist))

    households = {
        g: (v["households"].value if "households" in v and not v["households"].is_missing else None)
        for g, v in values.items()
    }

    from .sources import attitude

    attitude.ensure_template(shortlist, market.key)

    optional_sources = [
        ("bls_jobs", {}),
        ("rents", {}),
        ("census_bps", {"households": households}),
        ("schools", {}),
    ]
    for name, kwargs in optional_sources:
        try:
            module = __import__(f"screener.sources.{name}", fromlist=["collect"])
        except ImportError as exc:
            ctx.log(f"SKIPPED {name}: module not available ({exc})")
            failures[name] = f"module not available: {exc}"
            continue
        _merge(values, _run_source(ctx, name, module.collect, shortlist, failures, **kwargs))

    _merge(values, _run_source(ctx, "attitude", attitude.collect, shortlist, failures))

    # ------------------------------------------------------- 6. fill in the gaps
    scored_specs, context_specs, owner = registry()
    all_specs = {**scored_specs, **context_specs}
    for unit in shortlist:
        row = values.setdefault(unit.geoid, {})
        for key in all_specs:
            if key not in row:
                source_name = owner.get(key, "unknown source")
                row[key] = missing(
                    failures.get(source_name, f"not produced by {source_name}")
                )

    bundle = {
        "market": {
            "key": market.key,
            "name": market.name,
            "short_name": market.short_name,
            "geo_type": market.geo_type,
            "geo_type_reason": market.geo_type_reason.strip(),
            "trade_area_note": market.trade_area_note.strip(),
            "counties": market.counties,
            "employment_centers": [
                {"name": c.name, "lat": c.lat, "lon": c.lon, "note": c.note}
                for c in market.employment_centers
            ],
            "min_population": market.min_population,
            "max_distance_miles": market.max_distance_miles,
            "target_submarkets": market.target_submarkets,
            "notes": market.notes.strip(),
        },
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "universe_size": len(universe),
        "in_range_size": len(in_range),
        "shortlist_method": shortlist_method,
        "always_include_not_screened": unreachable_forced,
        "units": [_unit_to_dict(u) for u in shortlist],
        "values": {
            geoid: {k: v.to_dict() for k, v in row.items()}
            for geoid, row in values.items()
            if geoid in {u.geoid for u in shortlist}
        },
        "specs": {
            k: {
                "key": s.key, "label": s.label, "pillar": s.pillar,
                "higher_is_better": s.higher_is_better, "unit": s.unit,
                "decimals": s.decimals, "scored": s.scored,
                "description": s.description, "source_module": owner.get(k, ""),
            }
            for k, s in all_specs.items()
        },
        "provenance": provenance,
        "failures": failures,
    }
    return bundle


def save(bundle: dict, output_dir: Path) -> Path:
    market_dir = output_dir / bundle["market"]["key"]
    market_dir.mkdir(parents=True, exist_ok=True)
    path = market_dir / "raw.json"
    path.write_text(json.dumps(bundle, indent=2, default=str))
    return path


def load(market_key: str, output_dir: Path) -> dict:
    path = output_dir / market_key / "raw.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No data bundle at {path}. Run: python -m screener.cli fetch --market {market_key}"
        )
    return json.loads(path.read_text())
