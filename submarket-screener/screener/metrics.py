"""Central registry of every column the screen can produce.

Assembled from the source modules at import time so there is exactly one
definition of each metric, and so a weight in config/weights.yml that refers to
a metric nobody produces fails loudly instead of being ignored.
"""
from __future__ import annotations

import importlib

from .provenance import MetricSpec

# Module path, relative to screener.sources. Order here is the column order in
# the workbook.
SOURCE_MODULES = [
    "census_acs",
    "bls_jobs",
    "rents",
    "census_bps",
    "geo",
    "schools",
    "attitude",
]

PILLARS = ["demand", "rent", "supply", "location", "municipal"]

PILLAR_LABELS = {
    "demand": "Demand",
    "rent": "Rent",
    "supply": "Supply pressure",
    "location": "Location",
    "municipal": "Municipal attitude",
}


def load_source_modules() -> dict[str, object]:
    """Import every source module, skipping any that is not present yet."""
    loaded: dict[str, object] = {}
    for name in SOURCE_MODULES:
        try:
            loaded[name] = importlib.import_module(f".sources.{name}", package="screener")
        except ImportError as exc:
            print(f"  WARNING: source module '{name}' could not be imported: {exc}")
    return loaded


def registry() -> tuple[dict[str, MetricSpec], dict[str, MetricSpec], dict[str, str]]:
    """Return (scored metrics, context columns, metric key -> source module)."""
    scored: dict[str, MetricSpec] = {}
    context: dict[str, MetricSpec] = {}
    owner: dict[str, str] = {}
    for name, module in load_source_modules().items():
        for spec in getattr(module, "METRICS", []):
            if spec.key in scored:
                raise ValueError(
                    f"metric '{spec.key}' is defined by both "
                    f"{owner[spec.key]} and {name}"
                )
            scored[spec.key] = spec
            owner[spec.key] = name
        for spec in getattr(module, "CONTEXT_COLUMNS", []):
            context[spec.key] = spec
            owner.setdefault(spec.key, name)
    return scored, context, owner


def validate_weights(weights) -> list[str]:
    """Return a list of problems with config/weights.yml. Empty means it is fine."""
    scored, _, _ = registry()
    problems = []
    for key in weights.metrics:
        if key not in scored:
            problems.append(
                f"weights.yml lists metric '{key}' but no source module produces it"
            )
    for pillar in weights.pillars:
        if pillar not in PILLARS:
            problems.append(f"weights.yml lists unknown pillar '{pillar}'")
    for key, spec in scored.items():
        if key not in weights.metrics:
            problems.append(
                f"metric '{key}' exists but has no weight in weights.yml, so it "
                f"would be silently ignored"
            )
        if spec.pillar not in weights.pillars:
            problems.append(
                f"metric '{key}' belongs to pillar '{spec.pillar}' which has no weight"
            )
    return problems
