"""One page per market: the ranking, a position map, and the reasoning.

Self-contained HTML. No CDN, no tile server, no fonts to download, so it opens
on a plane. Print to PDF from the browser if you want to send it as a PDF.

The map is a plain scatter of submarket centroids drawn as inline SVG from the
Gazetteer coordinates, with the employment centres marked. It is a position
diagram, not a basemap. There is no free map tile service that works offline,
and a wrong basemap would be worse than none.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from .metrics import PILLAR_LABELS

CSS = """
:root { --ink:#16202c; --muted:#6b7785; --line:#dfe4ea; --top:#1f7a4d; --warn:#b4451f; }
* { box-sizing:border-box; }
body { font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
       color:var(--ink); margin:0; padding:28px 34px; background:#fff; max-width:1080px; }
h1 { font-size:24px; margin:0 0 2px; letter-spacing:-0.01em; }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted);
     margin:26px 0 8px; font-weight:600; }
.sub { color:var(--muted); font-size:12px; margin:0 0 4px; }
table { border-collapse:collapse; width:100%; font-size:13px; }
th { text-align:left; font-weight:600; font-size:11px; text-transform:uppercase;
     letter-spacing:0.04em; color:var(--muted); border-bottom:2px solid var(--line);
     padding:6px 8px; }
td { padding:6px 8px; border-bottom:1px solid var(--line); }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
tr.top td { background:#eef7f2; font-weight:600; }
.rank { width:34px; color:var(--muted); font-variant-numeric:tabular-nums; }
.why li { margin-bottom:6px; }
.grid { display:grid; grid-template-columns:1.25fr 1fr; gap:26px; align-items:start; }
.miss { color:var(--warn); }
.foot { margin-top:28px; padding-top:12px; border-top:1px solid var(--line);
        color:var(--muted); font-size:11px; }
.gaps { font-size:11px; color:var(--muted); }
.gaps td { padding:3px 8px; }
svg text { font:9px -apple-system,Helvetica,Arial,sans-serif; fill:var(--muted); }
@media print { body { padding:0; } h2 { margin-top:18px; } }
"""


def _svg_map(bundle: dict, ranked, width: int = 420, height: int = 340) -> str:
    units = {u["geoid"]: u for u in bundle["units"]}
    pts = [(u["lon"], u["lat"], u["name"], u["geoid"])
           for u in bundle["units"] if u["lat"] is not None and u["lon"] is not None]
    centers = [(c["lon"], c["lat"], c["name"])
               for c in bundle["market"]["employment_centers"]]
    if not pts:
        return "<p class='sub'>No coordinates available, so no map.</p>"

    lons = [p[0] for p in pts] + [c[0] for c in centers]
    lats = [p[1] for p in pts] + [c[1] for c in centers]
    pad = 0.06
    lon0, lon1 = min(lons) - pad, max(lons) + pad
    lat0, lat1 = min(lats) - pad, max(lats) + pad
    # Correct for the fact that a degree of longitude is shorter than a degree
    # of latitude away from the equator, so the shape is not stretched.
    import math

    kx = math.cos(math.radians((lat0 + lat1) / 2))
    span_x = max((lon1 - lon0) * kx, 1e-6)
    span_y = max(lat1 - lat0, 1e-6)
    scale = min((width - 60) / span_x, (height - 50) / span_y)

    def xy(lon, lat):
        x = 30 + (lon - lon0) * kx * scale
        y = height - 25 - (lat - lat0) * scale
        return round(x, 1), round(y, 1)

    rank_of = {r.geoid: r.rank for r in ranked if r.rank}
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
             f'aria-label="Submarket positions">']
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fafbfc" '
                 f'stroke="#dfe4ea"/>')
    for lon, lat, name in centers:
        x, y = xy(lon, lat)
        parts.append(f'<path d="M{x - 6},{y} L{x},{y - 6} L{x + 6},{y} L{x},{y + 6} Z" '
                     f'fill="#1f3864"/>')
        parts.append(f'<text x="{x + 9}" y="{y + 3}" fill="#1f3864">'
                     f'{html.escape(name[:26])}</text>')
    for lon, lat, name, geoid in pts:
        x, y = xy(lon, lat)
        rank = rank_of.get(geoid)
        top = rank is not None and rank <= 3
        fill = "#1f7a4d" if top else "#9aa6b2"
        r = 6 if top else 4
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" '
                     f'fill-opacity="0.85"/>')
        if top:
            parts.append(f'<text x="{x}" y="{y + 3}" text-anchor="middle" '
                         f'fill="#fff" font-weight="700">{rank}</text>')
            parts.append(f'<text x="{x + 9}" y="{y - 6}" fill="#1f7a4d" '
                         f'font-weight="600">{html.escape(name[:24])}</text>')
    parts.append(f'<text x="30" y="{height - 8}">Diamonds are employment centres. '
                 f'Green numbers are the top three.</text>')
    parts.append("</svg>")
    _ = units
    return "".join(parts)


def _fmt(spec: dict, value) -> str:
    if value is None:
        return '<span class="miss">MISSING</span>'
    if isinstance(value, (int, float)):
        text = f"{value:,.{spec['decimals']}f}"
        if spec["unit"] == "%":
            return text + "%"
        if spec["unit"] == "$":
            return "$" + text
        return text
    return html.escape(str(value))


def render(bundle: dict, ranked, explanation: list[str], weights, path: Path) -> Path:
    market = bundle["market"]
    specs = bundle["specs"]
    values = bundle["values"]
    pillars = [p for p in PILLAR_LABELS if any(p in r.pillars for r in ranked)]

    rows = []
    for r in ranked:
        cls = ' class="top"' if r.rank and r.rank <= 3 else ""
        cells = [f'<td class="rank">{r.rank or "-"}</td>',
                 f"<td>{html.escape(r.name)}</td>",
                 f'<td class="num">{"-" if r.total is None else f"{r.total:.1f}"}</td>']
        for p in pillars:
            ps = r.pillars.get(p)
            cells.append(
                f'<td class="num">'
                f'{"-" if ps is None or ps.score is None else f"{ps.score:.0f}"}</td>'
            )
        cells.append(f'<td class="num">{r.coverage * 100:.0f}%</td>')
        rows.append(f"<tr{cls}>{''.join(cells)}</tr>")

    headline_keys = [k for k in ("hh_cagr_5y", "renter_share", "zori_latest", "zori_yoy",
                                 "permits_5plus_3y_per_1k_hh", "miles_to_employment")
                     if k in specs]
    detail_rows = []
    for r in ranked[:5]:
        cells = [f"<td>{html.escape(r.name)}</td>"]
        for key in headline_keys:
            cell = values.get(r.geoid, {}).get(key) or {}
            cells.append(f'<td class="num">{_fmt(specs[key], cell.get("value"))}</td>')
        detail_rows.append(f"<tr>{''.join(cells)}</tr>")

    gap_rows = []
    for key, spec in specs.items():
        cells = [values.get(u["geoid"], {}).get(key) or {} for u in bundle["units"]]
        have = sum(1 for c in cells if c.get("value") is not None)
        if have < len(cells):
            reasons = [c.get("missing_reason", "") for c in cells if c.get("value") is None]
            common = max(set(reasons), key=reasons.count) if reasons else ""
            gap_rows.append(
                f"<tr><td>{html.escape(spec['label'])}</td>"
                f'<td class="num">{have}/{len(cells)}</td>'
                f"<td>{html.escape(common[:150])}</td></tr>"
            )

    sources = {}
    for key in specs:
        for u in bundle["units"]:
            cell = values.get(u["geoid"], {}).get(key) or {}
            if cell.get("source"):
                sources.setdefault(cell["source"], set()).add(cell.get("vintage", ""))
                break

    source_list = "".join(
        f"<li><b>{html.escape(s)}</b>: "
        f"{html.escape(', '.join(sorted(v for v in vs if v)) or 'vintage not recorded')}</li>"
        for s, vs in sorted(sources.items())
    )

    weight_line = ", ".join(
        f"{PILLAR_LABELS[p]} {weights.pillars[p]:.0f}"
        for p in PILLAR_LABELS if weights.pillars.get(p, 0) > 0
    )

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{html.escape(market['name'])} submarket screen</title>
<style>{CSS}</style></head><body>
<h1>{html.escape(market['name'])}: submarket screen</h1>
<p class="sub">{len(bundle['units'])} submarkets screened from {bundle['in_range_size']}
within {market['max_distance_miles']:.0f} miles of an employment centre, out of
{bundle['universe_size']} in the trade area. Geography: {market['geo_type'].replace('_', ' ')}.
Weights: {weight_line}. Scoring: {weights.scoring_method}.</p>
<p class="sub">Data built {bundle['built_at']}. Page generated
{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.</p>

<div class="grid">
 <div>
  <h2>Ranking</h2>
  <table><thead><tr><th class="rank">#</th><th>Submarket</th><th class="num">Score</th>
  {''.join(f'<th class="num">{PILLAR_LABELS[p]}</th>' for p in pillars)}
  <th class="num">Coverage</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
 </div>
 <div>
  <h2>Where they are</h2>
  {_svg_map(bundle, ranked)}
 </div>
</div>

<h2>Why the top submarket ranks first</h2>
<ul class="why">{''.join(f'<li>{html.escape(line)}</li>' for line in explanation)}</ul>

<h2>Headline figures, top five</h2>
<table><thead><tr><th>Submarket</th>
{''.join(f'<th class="num">{html.escape(specs[k]["label"])}</th>' for k in headline_keys)}
</tr></thead><tbody>{''.join(detail_rows)}</tbody></table>

<h2>What is missing</h2>
{'<table class="gaps"><thead><tr><th>Column</th><th class="num">Have</th><th>Reason</th></tr></thead><tbody>' + ''.join(gap_rows) + '</tbody></table>' if gap_rows else '<p class="sub">Nothing. Every column has a figure for every submarket.</p>'}

<h2>Sources</h2>
<ul class="gaps">{source_list}</ul>

<p class="foot">Trade area: {html.escape(market['trade_area_note'])}<br>
Geography choice: {html.escape(market['geo_type_reason'])}<br>
This is a screen built from free public data. It says which municipalities are
worth a week of work. It is not an underwriting and it is not a site selection.</p>
</body></html>"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    return path
