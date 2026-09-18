"""Municipal attitude to rental housing: the manual column.

This is the one input that cannot be automated honestly. Whether a village
board will entertain a 300-unit garden-style community is a function of who
sits on the plan commission, what happened at the last rezoning hearing, and
whether the comprehensive plan has a multifamily land use category with any
land actually mapped to it. No API returns that.

So it is a manual column. You research it, you type it in, and the screen
scores it. Anything you have not researched scores as MISSING, not as neutral,
so an unresearched municipality can never quietly prop up a ranking.

Ratings: supportive, leaning_supportive, neutral, leaning_hostile, hostile
Scores come from config/weights.yml under attitude_scores, so you can change
how much a hostile council actually costs a submarket.

# LIMITATIONS
- It is a judgement call, and it is yours. The workbook records who entered it
  and when so a reader knows it is an opinion, not a measurement.
- Council composition changes. A rating older than about a year is stale, and
  the workbook shows the date you entered it so that is visible.
- The optional web-search draft notes are UNVERIFIED. They are a starting point
  for your own reading, never a citation.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..config import CONFIG_DIR
from ..context import Context
from ..provenance import MetricSpec, Unit, Value, missing

SOURCE_NAME = "Manual research (analyst input)"
ATTITUDE_CSV = CONFIG_DIR / "municipal_attitude.csv"

VALID_RATINGS = [
    "supportive", "leaning_supportive", "neutral", "leaning_hostile", "hostile",
]

FIELDNAMES = [
    "market", "geoid", "submarket", "rating", "notes",
    "evidence_url", "researched_by", "researched_on", "unverified_ai_draft",
]

METRICS = [
    MetricSpec("municipal_attitude", "Municipal attitude to rental housing", "municipal",
               True, "score", 0,
               description="Manual 0 to 100 rating of how the municipality treats new "
                           "market-rate rental development."),
]

CONTEXT_COLUMNS = [
    MetricSpec("municipal_rating", "Municipal rating (text)", "municipal", True, "", 0, scored=False),
    MetricSpec("municipal_notes", "Municipal notes", "municipal", True, "", 0, scored=False),
    MetricSpec("municipal_evidence_url", "Municipal evidence link", "municipal", True, "", 0, scored=False),
    MetricSpec("municipal_researched_on", "Municipal rating date", "municipal", True, "", 0, scored=False),
    MetricSpec("municipal_unverified_draft", "Unverified AI draft note", "municipal", True, "", 0, scored=False),
]


def ensure_template(units: list[Unit], market_key: str, path: Path | None = None) -> Path:
    """Create or extend the manual CSV so every submarket has a row to fill in."""
    path = path or ATTITUDE_CSV
    existing: dict[tuple[str, str], dict] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                existing[(row.get("market", ""), row.get("geoid", ""))] = row

    for unit in units:
        key = (market_key, unit.geoid)
        if key not in existing:
            existing[key] = {
                "market": market_key,
                "geoid": unit.geoid,
                "submarket": unit.name,
                "rating": "",
                "notes": "",
                "evidence_url": "",
                "researched_by": "",
                "researched_on": "",
                "unverified_ai_draft": "",
            }
        else:
            existing[key]["submarket"] = unit.name

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        for key in sorted(existing):
            row = existing[key]
            writer.writerow({f: row.get(f, "") for f in FIELDNAMES})
    return path


def collect(ctx: Context, units: list[Unit], path: Path | None = None
            ) -> dict[str, dict[str, Value]]:
    path = path or ATTITUDE_CSV
    scores = ctx.weights.attitude_scores
    rows: dict[str, dict] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("market") == ctx.market.key:
                    rows[row.get("geoid", "")] = row

    filled = 0
    out: dict[str, dict[str, Value]] = {}
    for unit in units:
        row = rows.get(unit.geoid, {})
        rating = (row.get("rating") or "").strip().lower().replace(" ", "_")
        researched_on = (row.get("researched_on") or "").strip()
        researched_by = (row.get("researched_by") or "").strip()
        notes_text = (row.get("notes") or "").strip()
        evidence = (row.get("evidence_url") or "").strip()
        draft = (row.get("unverified_ai_draft") or "").strip()

        entry: dict[str, Value] = {}
        if not rating:
            entry["municipal_attitude"] = missing(
                "not yet researched. Fill in config/municipal_attitude.csv. "
                "Left blank on purpose so it cannot quietly score as neutral.",
                source=SOURCE_NAME,
            )
        elif rating not in scores:
            entry["municipal_attitude"] = missing(
                f"rating '{rating}' is not one of {VALID_RATINGS}",
                source=SOURCE_NAME,
            )
        else:
            filled += 1
            entry["municipal_attitude"] = Value(
                float(scores[rating]),
                source=SOURCE_NAME,
                vintage=f"entered {researched_on or 'date not recorded'}",
                url=evidence,
                retrieved_at=researched_on,
                notes=(f"Analyst rating '{rating}'"
                       + (f" by {researched_by}" if researched_by else "")
                       + ". This is a judgement, not a measurement. "
                       + (notes_text or "No note recorded.")),
            )

        entry["municipal_rating"] = Value(rating or None, source=SOURCE_NAME,
                                          missing_reason="not yet researched")
        entry["municipal_notes"] = Value(notes_text or None, source=SOURCE_NAME,
                                         missing_reason="no note entered")
        entry["municipal_evidence_url"] = Value(evidence or None, source=SOURCE_NAME,
                                                missing_reason="no evidence link entered")
        entry["municipal_researched_on"] = Value(researched_on or None, source=SOURCE_NAME,
                                                 missing_reason="no date entered")
        entry["municipal_unverified_draft"] = Value(
            draft or None,
            source="AI web-search draft, UNVERIFIED",
            notes="Drafted from a web search. Not a citation. Read the source "
                  "yourself before repeating any of it.",
            missing_reason="no draft generated",
        )
        out[unit.geoid] = entry

    ctx.log(f"Municipal attitude: {filled} of {len(units)} submarkets rated")
    return out
