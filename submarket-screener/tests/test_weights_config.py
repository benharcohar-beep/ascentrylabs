"""config/weights.yml must stay in step with the metrics that actually exist.

Two failure modes, both invisible in the output, which is why this is pinned:

  a weight naming a metric no source module produces is silently ignored, so a
  pillar quietly carries less than you think;

  a metric with no weight is silently dropped from the score, so a column you
  can see in the workbook contributes nothing to the ranking.

The same check lives inside `screener.cli check`, but that command also exits
non-zero when the API keys are absent, which they always are in CI. Keeping the
weights half here means it runs on every push.
"""
from __future__ import annotations

from screener.config import load_market, list_markets, load_weights
from screener.metrics import PILLARS, registry, validate_weights


def test_shipped_weights_are_consistent_with_the_metric_registry():
    problems = validate_weights(load_weights())
    assert not problems, "config/weights.yml is out of step:\n" + "\n".join(problems)


def test_every_pillar_carries_some_weight():
    weights = load_weights()
    for pillar in PILLARS:
        assert weights.pillars.get(pillar, 0) > 0, (
            f"pillar '{pillar}' has no weight, so every metric in it is dead code"
        )


def test_every_scored_metric_belongs_to_a_real_pillar():
    scored, _, _ = registry()
    assert scored, "no scored metrics were registered at all"
    for key, spec in scored.items():
        assert spec.pillar in PILLARS, f"metric '{key}' has unknown pillar '{spec.pillar}'"


def test_every_market_config_loads_and_names_a_supported_geography():
    keys = list_markets()
    assert keys, "no market configs found"
    for key in keys:
        market = load_market(key)
        assert market.geo_type in {"place", "county_subdivision"}
        assert market.counties, f"{key} has no counties"
        for county in market.counties:
            assert len(county["fips"]) == 5 and county["fips"].isdigit(), (
                f"{key}: county FIPS '{county['fips']}' is not 5 digits"
            )
            assert county["fips"][:2] in market.states, (
                f"{key}: county {county['fips']} is not in a state this market lists"
            )
        assert market.employment_centers, (
            f"{key} has no employment centres, so the trade area filter would "
            f"drop every municipality"
        )
