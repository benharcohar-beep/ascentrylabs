"""Interview demo: move the weights, watch the ranking move.

Reads output/<market>/raw.json only. It never touches the network, so it works
on conference wifi or none at all. Run it with:

    streamlit run app/streamlit_app.py

If a market is missing from the dropdown, run the fetch step for it first.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from screener import assemble, score                      # noqa: E402
from screener.config import OUTPUT_DIR, load_weights      # noqa: E402
from screener.metrics import PILLAR_LABELS, PILLARS       # noqa: E402

st.set_page_config(page_title="Submarket screen", layout="wide")


@st.cache_data(show_spinner=False)
def available_markets() -> list[str]:
    return sorted(p.parent.name for p in OUTPUT_DIR.glob("*/raw.json"))


@st.cache_data(show_spinner=False)
def load_bundle(key: str) -> dict:
    return assemble.load(key, OUTPUT_DIR)


markets = available_markets()
if not markets:
    st.error(
        "No data found in output/. Run this first, with a network connection:\n\n"
        "    python -m screener.cli fetch --all"
    )
    st.stop()

weights = load_weights()

st.sidebar.title("Weights")
st.sidebar.caption(
    "These start at the values in config/weights.yml. Moving them here does not "
    "change that file, so the saved workbook keeps the agreed weighting."
)

market_key = st.sidebar.selectbox(
    "Market", markets,
    format_func=lambda k: load_bundle(k)["market"]["name"],
)
bundle = load_bundle(market_key)
specs = bundle["specs"]

method = st.sidebar.radio(
    "Scoring method", ["percentile", "zscore"],
    index=0 if weights.scoring_method == "percentile" else 1,
    help=(
        "percentile: where a submarket sits in the pack, 0 worst and 100 best. "
        "zscore: 50 plus 15 points per standard deviation above the market average, "
        "which rewards being far ahead rather than just ahead."
    ),
)

st.sidebar.subheader("Pillars")
pillar_weights = {}
for pillar in PILLARS:
    default = float(weights.pillars.get(pillar, 0))
    pillar_weights[pillar] = st.sidebar.slider(
        PILLAR_LABELS[pillar], 0.0, 60.0, default, 1.0, key=f"p_{pillar}"
    )

total_w = sum(pillar_weights.values())
if total_w <= 0:
    st.sidebar.error("At least one pillar needs a weight above zero.")
    st.stop()
st.sidebar.caption(
    "Sum: " + f"{total_w:.0f}" + ". Weights are normalised, so the sum does not matter."
)

with st.sidebar.expander("Metric weights inside each pillar"):
    metric_weights = {}
    for pillar in PILLARS:
        keys = [k for k, s in specs.items() if s["scored"] and s["pillar"] == pillar]
        if not keys or pillar_weights[pillar] <= 0:
            continue
        st.markdown(f"**{PILLAR_LABELS[pillar]}**")
        for key in keys:
            metric_weights[key] = st.slider(
                specs[key]["label"], 0.0, 100.0,
                float(weights.metrics.get(key, 0)), 5.0, key=f"m_{key}",
            )

for key, spec in specs.items():
    if spec["scored"]:
        metric_weights.setdefault(key, float(weights.metrics.get(key, 0)))

ranked = score.score_market(
    bundle, weights, method=method,
    pillar_weights=pillar_weights, metric_weights=metric_weights,
)
explanation = score.explain(bundle, ranked)

st.title(bundle["market"]["name"] + ": submarket screen")
st.caption(
    f"{len(bundle['units'])} submarkets screened from {bundle['in_range_size']} within "
    f"{bundle['market']['max_distance_miles']:.0f} miles of an employment centre. "
    f"Geography: {bundle['market']['geo_type'].replace('_', ' ')}. "
    f"Data built {bundle['built_at']}. Nothing here is downloaded live."
)

active = [p for p in PILLARS if pillar_weights[p] > 0]
rows = []
for r in ranked:
    row = {
        "Rank": r.rank or "",
        "Submarket": r.name,
        "Score": r.total,
        **{PILLAR_LABELS[p]: (r.pillars[p].score if p in r.pillars else None)
           for p in active},
        "Coverage": r.coverage,
    }
    rows.append(row)
table = pd.DataFrame(rows)

left, right = st.columns([3, 2])

with left:
    st.subheader("Ranking")
    st.dataframe(
        table.style
        .format({"Score": "{:.1f}", "Coverage": "{:.0%}",
                 **{PILLAR_LABELS[p]: "{:.0f}" for p in active}}, na_rep="n/a")
        .apply(lambda s: ["background-color:#e8f4ed" if i < 3 else "" for i in range(len(s))],
               axis=0),
        use_container_width=True, hide_index=True, height=460,
    )

with right:
    st.subheader("Why the top submarket ranks first")
    for line in explanation:
        st.markdown(f"- {line}")

    thin = [r.name for r in ranked if r.thin_data]
    if thin:
        st.warning(
            "Thin data, treat the rank with care: " + ", ".join(thin)
            + ". Coverage below 60% of the intended weighting."
        )

st.divider()
tab_detail, tab_raw, tab_gaps, tab_method = st.tabs(
    ["Score detail", "Raw data", "What is missing", "How the scoring works"]
)

with tab_detail:
    pick = st.selectbox("Submarket", [r.name for r in ranked])
    chosen = next(r for r in ranked if r.name == pick)
    detail = []
    for pillar, ps in chosen.pillars.items():
        for key, ms in ps.metrics.items():
            detail.append({
                "Pillar": PILLAR_LABELS[pillar],
                "Metric": specs[key]["label"],
                "Raw value": ms.raw,
                "Sub-score 0-100": ms.sub_score,
                "Weight": metric_weights.get(key, 0),
                "Direction": "high good" if specs[key]["higher_is_better"] else "low good",
                "If missing, why": ms.missing_reason,
            })
    st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)

with tab_raw:
    raw_rows = []
    for unit in bundle["units"]:
        row = {"Submarket": unit["name"], "County": unit["county_name"]}
        for key, spec in specs.items():
            cell = bundle["values"].get(unit["geoid"], {}).get(key) or {}
            row[spec["label"]] = cell.get("value") if cell.get("value") is not None else "MISSING"
        raw_rows.append(row)
    st.dataframe(pd.DataFrame(raw_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Sources and vintages for every column are on the 'Sources and gaps' tab of "
        "the Excel workbook and in the README."
    )

with tab_gaps:
    gap_rows = []
    for key, spec in specs.items():
        cells = [bundle["values"].get(u["geoid"], {}).get(key) or {} for u in bundle["units"]]
        have = sum(1 for c in cells if c.get("value") is not None)
        if have == len(cells):
            continue
        reasons = [c.get("missing_reason", "") for c in cells if c.get("value") is None]
        gap_rows.append({
            "Column": spec["label"],
            "Have": f"{have} of {len(cells)}",
            "Most common reason": max(set(reasons), key=reasons.count) if reasons else "",
        })
    if gap_rows:
        st.dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)
    else:
        st.success("Every column has a figure for every submarket.")
    if bundle.get("failures"):
        st.subheader("Sources that failed or were skipped")
        for name, msg in bundle["failures"].items():
            st.markdown(f"**{name}**: {msg}")

with tab_method:
    st.markdown(score.__doc__)
