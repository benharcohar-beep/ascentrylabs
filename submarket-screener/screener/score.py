"""Turning raw figures into a ranking.

The maths, in plain English, is three steps.

STEP 1: make the columns comparable.
  Median household income is in dollars, rent growth is in percent, distance is
  in miles. You cannot add them together. So each column is converted to a 0 to
  100 sub-score that says where a submarket sits relative to the other
  submarkets in the SAME market. Two ways to do that, set in weights.yml:

    percentile  (default) 0 means the worst of the group, 100 the best, and the
                number in between is the share of the group this submarket
                beats. It is the same calculation as Excel's PERCENTRANK.INC,
                on purpose, so the workbook's live formulas give exactly the
                same answer as this code.

    zscore      50 plus 15 times the number of standard deviations above the
                group average, clipped to 0 and 100. This one rewards being far
                ahead rather than just being ahead.

  For a column where low is good (permits per household, miles to work,
  unemployment) the sub-score is flipped, so 100 always means "good for us".

STEP 2: average the sub-scores inside each pillar.
  Weighted by the metric weights in weights.yml. If a figure is missing for a
  submarket, it is dropped and the remaining weights inside that pillar are
  rescaled so they still add to 100%. Nothing is filled in with a zero or an
  average.

STEP 3: average the pillars into one score.
  Weighted by the pillar weights. If a whole pillar has no data for a
  submarket, its weight is redistributed across the pillars that do. The
  workbook reports what share of the intended weight each submarket actually
  had data for, under "Data coverage", so a submarket that ranks well on three
  columns out of thirteen is visibly not the same as one that ranks well on
  thirteen out of thirteen.

The whole thing is deliberately a screen, not a valuation. It tells you which
five municipalities to spend a week on. It does not tell you what to pay.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

Z_SCALE = 15.0          # one standard deviation is worth 15 points
Z_CENTRE = 50.0
COVERAGE_WARN = 0.60    # below this share of intended weight, flag the row


@dataclass
class MetricScore:
    key: str
    raw: float | None
    sub_score: float | None
    missing_reason: str = ""


@dataclass
class PillarScore:
    pillar: str
    score: float | None
    weight_used: float
    coverage: float                      # share of the pillar's metric weight with data
    metrics: dict[str, MetricScore] = field(default_factory=dict)


@dataclass
class UnitScore:
    geoid: str
    name: str
    total: float | None
    coverage: float
    pillars: dict[str, PillarScore]
    rank: int | None = None
    thin_data: bool = False


def percentrank_inc(values: list[float], x: float) -> float | None:
    """Excel's PERCENTRANK.INC for a value that is in the array, as 0 to 100.

    Excel returns (count of values strictly below x) / (n - 1). Ties therefore
    take the lowest of the tied ranks, which is what Excel does too. This is
    reimplemented rather than approximated so the Python ranking and the
    workbook's live formulas cannot drift apart.
    """
    n = len(values)
    if n < 2:
        return None
    below = sum(1 for v in values if v < x)
    return 100.0 * below / (n - 1)


def zscore_points(values: list[float], x: float) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean = statistics.fmean(values)
    # Population standard deviation, matching Excel's STDEV.P used in the workbook.
    sd = statistics.pstdev(values)
    if sd == 0:
        return Z_CENTRE
    return max(0.0, min(100.0, Z_CENTRE + Z_SCALE * (x - mean) / sd))


def _sub_score(method: str, values: list[float], x: float, higher_is_better: bool
               ) -> float | None:
    if method == "zscore":
        raw = zscore_points(values, x)
    else:
        raw = percentrank_inc(values, x)
    if raw is None:
        return None
    return raw if higher_is_better else 100.0 - raw


def score_market(bundle: dict, weights, *, method: str | None = None,
                 pillar_weights: dict[str, float] | None = None,
                 metric_weights: dict[str, float] | None = None) -> list[UnitScore]:
    """Score and rank one market bundle.

    pillar_weights and metric_weights let the Streamlit app override the YAML
    without writing to disk. Everything else comes from the bundle, so this
    function never touches the network.
    """
    method = method or weights.scoring_method
    pillar_w = dict(pillar_weights or weights.pillars)
    metric_w = dict(metric_weights or weights.metrics)

    specs = bundle["specs"]
    units = bundle["units"]
    values = bundle["values"]

    scored_keys = [k for k, s in specs.items() if s["scored"]]

    # Column of raw values across the market, for the relative scoring.
    columns: dict[str, list[float]] = {}
    for key in scored_keys:
        col = []
        for unit in units:
            cell = values.get(unit["geoid"], {}).get(key)
            if cell and cell.get("value") is not None:
                try:
                    col.append(float(cell["value"]))
                except (TypeError, ValueError):
                    pass
        columns[key] = col

    total_pillar_weight = sum(w for w in pillar_w.values() if w > 0)
    results: list[UnitScore] = []

    for unit in units:
        geoid = unit["geoid"]
        pillars: dict[str, PillarScore] = {}

        for pillar, p_weight in pillar_w.items():
            if p_weight <= 0:
                continue
            keys = [k for k in scored_keys if specs[k]["pillar"] == pillar]
            numerator = 0.0
            weight_with_data = 0.0
            weight_intended = 0.0
            metric_scores: dict[str, MetricScore] = {}

            for key in keys:
                m_weight = float(metric_w.get(key, 0.0))
                if m_weight <= 0:
                    continue
                weight_intended += m_weight
                cell = values.get(geoid, {}).get(key) or {}
                raw = cell.get("value")
                try:
                    raw_f = float(raw) if raw is not None else None
                except (TypeError, ValueError):
                    raw_f = None

                if raw_f is None:
                    metric_scores[key] = MetricScore(
                        key, None, None, cell.get("missing_reason", "missing")
                    )
                    continue

                sub = _sub_score(method, columns[key], raw_f, specs[key]["higher_is_better"])
                metric_scores[key] = MetricScore(key, raw_f, sub)
                if sub is not None:
                    numerator += sub * m_weight
                    weight_with_data += m_weight

            have = sum(1 for m in metric_scores.values() if m.sub_score is not None)
            coverage = weight_with_data / weight_intended if weight_intended else 0.0
            if have >= weights.min_metrics_per_pillar and weight_with_data > 0:
                pillars[pillar] = PillarScore(
                    pillar, numerator / weight_with_data, p_weight, coverage, metric_scores
                )
            else:
                pillars[pillar] = PillarScore(pillar, None, p_weight, coverage, metric_scores)

        live = {p: ps for p, ps in pillars.items() if ps.score is not None}
        live_weight = sum(ps.weight_used for ps in live.values())
        if live_weight > 0:
            total = sum(ps.score * ps.weight_used for ps in live.values()) / live_weight
        else:
            total = None

        # Coverage is the share of the INTENDED total weight that had data,
        # counting partial coverage inside a pillar.
        covered = sum(
            ps.weight_used * ps.coverage for ps in pillars.values()
        )
        coverage = covered / total_pillar_weight if total_pillar_weight else 0.0

        results.append(
            UnitScore(
                geoid=geoid,
                name=unit["name"],
                total=None if total is None else round(total, 2),
                coverage=round(coverage, 4),
                pillars=pillars,
                thin_data=coverage < COVERAGE_WARN,
            )
        )

    ranked = sorted(
        results,
        key=lambda r: (r.total is None, -(r.total if r.total is not None else 0.0)),
    )
    for i, res in enumerate(ranked, start=1):
        res.rank = i if res.total is not None else None
    return ranked


def explain(bundle: dict, scores: list[UnitScore], top_n: int = 3) -> list[str]:
    """Plain sentences about why the leader leads. No adjectives, just the columns."""
    specs = bundle["specs"]
    ranked = [s for s in scores if s.total is not None]
    if not ranked:
        return ["No submarket could be scored. Every input was missing."]

    leader = ranked[0]
    lines = []

    # Which pillars is the leader strongest on, relative to the group average?
    pillar_means: dict[str, float] = {}
    for pillar in leader.pillars:
        vals = [s.pillars[pillar].score for s in ranked
                if pillar in s.pillars and s.pillars[pillar].score is not None]
        if vals:
            pillar_means[pillar] = statistics.fmean(vals)

    gaps = []
    for pillar, ps in leader.pillars.items():
        if ps.score is not None and pillar in pillar_means:
            gaps.append((ps.score - pillar_means[pillar], pillar, ps.score))
    gaps.sort(reverse=True)

    from .metrics import PILLAR_LABELS

    runner_up = ranked[1] if len(ranked) > 1 else None
    if runner_up:
        lines.append(
            f"{leader.name} ranks first with a weighted score of {leader.total:.1f}, "
            f"ahead of {runner_up.name} on {runner_up.total:.1f}."
        )
    else:
        lines.append(
            f"{leader.name} ranks first with a weighted score of {leader.total:.1f}. "
            f"It was the only submarket with enough data to score."
        )

    for gap, pillar, score in gaps[:2]:
        label = PILLAR_LABELS.get(pillar, pillar).lower()
        best_metric = None
        best_sub = -1.0
        for key, ms in leader.pillars[pillar].metrics.items():
            if ms.sub_score is not None and ms.sub_score > best_sub:
                best_sub, best_metric = ms.sub_score, key
        if best_metric:
            spec = specs[best_metric]
            raw = leader.pillars[pillar].metrics[best_metric].raw
            shown = f"{raw:,.{spec['decimals']}f}{spec['unit'] if spec['unit'] == '%' else ''}"
            lines.append(
                f"It leads on {label}, scoring {score:.0f} out of 100 against a "
                f"group average of {pillar_means[pillar]:.0f}, driven mainly by "
                f"{spec['label'].lower()} of {shown}."
            )
        else:
            lines.append(
                f"It leads on {label}, scoring {score:.0f} out of 100 against a "
                f"group average of {pillar_means[pillar]:.0f}."
            )

    weakest = [g for g in gaps if g[0] < 0]
    if weakest:
        _, pillar, score = weakest[-1]
        lines.append(
            f"The case is not clean: it scores {score:.0f} out of 100 on "
            f"{PILLAR_LABELS.get(pillar, pillar).lower()}, below the group average "
            f"of {pillar_means[pillar]:.0f}, and that is the first thing to test."
        )

    if leader.coverage < 1.0:
        lines.append(
            f"Data coverage for {leader.name} is {leader.coverage * 100:.0f}% of the "
            f"intended weighting, so the score rests on the columns that were "
            f"available and the missing ones are listed in the raw tab."
        )
    return lines
