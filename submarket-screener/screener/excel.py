"""The workbook: one raw tab, one scoring tab with live formulas, one ranking tab.

The scoring tab is not a dump of numbers this code already worked out. It
recalculates inside Excel from the weights at the top of the sheet, using the
same PERCENTRANK.INC that screener/score.py reimplements. Change a weight in
the yellow cells and the ranking tab reorders. That is the point: an
interviewer can take the keyboard.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .metrics import PILLARS, PILLAR_LABELS
from .score import COVERAGE_WARN as COVERAGE_PENALTY_THRESHOLD

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
PILLAR_FILL = PatternFill("solid", fgColor="D9E2F3")
EDIT_FILL = PatternFill("solid", fgColor="FFF2CC")
META_FILL = PatternFill("solid", fgColor="F2F2F2")
TOP3_FILL = PatternFill("solid", fgColor="C6EFCE")
MISSING_FILL = PatternFill("solid", fgColor="FCE4D6")

WHITE_BOLD = Font(color="FFFFFF", bold=True)
SMALL_GREY = Font(size=8, color="808080")
BOLD = Font(bold=True)
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

RAW_META_ROWS = ["Source", "Vintage", "Retrieved", "Source URL", "Direction", "Metric key"]
RAW_DATA_START = 2 + len(RAW_META_ROWS)      # header row 1, then metadata, then data


def _ordered_metrics(specs: dict) -> list[str]:
    """Scored metrics grouped by pillar, in pillar order, so Excel ranges are contiguous."""
    out = []
    for pillar in PILLARS:
        out.extend(
            k for k, s in specs.items() if s["scored"] and s["pillar"] == pillar
        )
    return out


def _ordered_context(specs: dict) -> list[str]:
    return [k for k, s in specs.items() if not s["scored"]]


def _number_format(spec: dict) -> str:
    if spec["unit"] == "$":
        return "#,##0" if spec["decimals"] == 0 else f"#,##0.{'0' * spec['decimals']}"
    if spec["decimals"] == 0:
        return "#,##0"
    return f"#,##0.{'0' * spec['decimals']}"


# --------------------------------------------------------------------- raw tab
def _write_raw(wb: Workbook, bundle: dict) -> dict[str, int]:
    ws = wb.create_sheet("Raw data")
    specs = bundle["specs"]
    units = bundle["units"]
    values = bundle["values"]

    columns = ["submarket", "geoid", "county", "population_note"]
    metric_keys = _ordered_metrics(specs) + _ordered_context(specs)

    fixed_labels = ["Submarket", "GEOID", "County", "Geography type"]
    for i, label in enumerate(fixed_labels, start=1):
        cell = ws.cell(row=1, column=i, value=label)
        cell.fill = HEADER_FILL
        cell.font = WHITE_BOLD
        cell.alignment = Alignment(wrap_text=True, vertical="bottom")

    col_of: dict[str, int] = {}
    for offset, key in enumerate(metric_keys):
        col = len(fixed_labels) + 1 + offset
        col_of[key] = col
        spec = specs[key]
        label = spec["label"] + (f" ({spec['unit']})" if spec["unit"] in ("%", "$") else "")
        cell = ws.cell(row=1, column=col, value=label)
        cell.fill = HEADER_FILL
        cell.font = WHITE_BOLD
        cell.alignment = Alignment(wrap_text=True, vertical="bottom")

    # Metadata rows. Source comes from the first cell that has one. Vintage is
    # NOT assumed to be uniform: several columns legitimately carry different
    # vintages per row (ZORI picks each submarket's own latest month, QCEW and
    # LAUS probe back per county to the newest year that is not suppressed), so
    # where a column mixes vintages the header says so rather than printing one
    # row's vintage over the whole column.
    for r, row_label in enumerate(RAW_META_ROWS, start=2):
        lab = ws.cell(row=r, column=1, value=row_label)
        lab.font = SMALL_GREY
        lab.fill = META_FILL
        for col in range(2, len(fixed_labels) + 1):
            ws.cell(row=r, column=col).fill = META_FILL

    for key, col in col_of.items():
        spec = specs[key]
        sample = None
        for unit in units:
            cell = values.get(unit["geoid"], {}).get(key)
            if cell and cell.get("source"):
                sample = cell
                if cell.get("value") is not None:
                    break
        vintages = sorted({
            (values.get(u["geoid"], {}).get(key) or {}).get("vintage", "")
            for u in units
            if (values.get(u["geoid"], {}).get(key) or {}).get("value") is not None
        } - {""})
        if len(vintages) > 1:
            vintage_text = f"MIXED ({len(vintages)}): " + "; ".join(vintages)
        elif vintages:
            vintage_text = vintages[0]
        else:
            vintage_text = (sample or {}).get("vintage", "")

        meta = {
            "Source": (sample or {}).get("source", ""),
            "Vintage": vintage_text,
            "Retrieved": (sample or {}).get("retrieved_at", ""),
            "Source URL": (sample or {}).get("url", ""),
            "Direction": ("higher is better" if spec["higher_is_better"] else "lower is better")
            if spec["scored"] else "context only, not scored",
            "Metric key": key,
        }
        for r, row_label in enumerate(RAW_META_ROWS, start=2):
            c = ws.cell(row=r, column=col, value=meta[row_label])
            c.font = SMALL_GREY
            c.fill = META_FILL
            c.alignment = Alignment(wrap_text=True, vertical="top")

    for i, unit in enumerate(units):
        r = RAW_DATA_START + i
        ws.cell(row=r, column=1, value=unit["name"]).font = BOLD
        ws.cell(row=r, column=2, value=unit["geoid"])
        ws.cell(row=r, column=3, value=unit["county_name"] or "not resolved")
        ws.cell(row=r, column=4, value=unit["geo_type"].replace("_", " "))
        for key, col in col_of.items():
            cell_data = values.get(unit["geoid"], {}).get(key) or {}
            value = cell_data.get("value")
            target = ws.cell(row=r, column=col)
            if value is None:
                target.value = "MISSING"
                target.fill = MISSING_FILL
                target.font = Font(size=9, italic=True, color="9C0006")
                reason = cell_data.get("missing_reason", "")
                if reason:
                    target.comment = _comment(f"MISSING: {reason}")
            else:
                target.value = value
                if isinstance(value, (int, float)):
                    target.number_format = _number_format(specs[key])
                note = cell_data.get("notes", "")
                if note:
                    target.comment = _comment(note)
            target.border = BOX

    ws.freeze_panes = ws.cell(row=RAW_DATA_START, column=2)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18
    for col in col_of.values():
        ws.column_dimensions[get_column_letter(col)].width = 16
    for r in range(2, 2 + len(RAW_META_ROWS)):
        ws.row_dimensions[r].height = 28
    return col_of


def _comment(text: str):
    from openpyxl.comments import Comment

    return Comment(text[:2000], "Submarket screener")


# ----------------------------------------------------------------- scoring tab
def _write_scoring(wb: Workbook, bundle: dict, weights, raw_cols: dict[str, int]) -> dict:
    ws = wb.create_sheet("Scoring")
    specs = bundle["specs"]
    units = bundle["units"]
    metric_keys = _ordered_metrics(specs)
    n = len(units)
    method = weights.scoring_method
    min_metrics = max(1, int(weights.min_metrics_per_pillar))

    raw_first = RAW_DATA_START
    raw_last = RAW_DATA_START + n - 1

    ws["A1"] = f"{bundle['market']['name']} submarket scoring"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = (
        f"Scoring method: {method}. Every yellow cell is editable and everything "
        f"below recalculates. Pillar weights do not have to sum to 100."
    )
    ws["A2"].font = SMALL_GREY

    # ---- pillar weights block
    ws["A4"] = "Pillar weights"
    ws["A4"].font = BOLD
    active_pillars = [p for p in PILLARS if weights.pillars.get(p, 0) > 0]
    for i, pillar in enumerate(active_pillars):
        col = 1 + i
        lab = ws.cell(row=5, column=col, value=PILLAR_LABELS[pillar])
        lab.font = BOLD
        lab.fill = PILLAR_FILL
        val = ws.cell(row=6, column=col, value=float(weights.pillars[pillar]))
        val.fill = EDIT_FILL
        val.border = BOX
    total_col = 1 + len(active_pillars)
    ws.cell(row=5, column=total_col, value="Total").font = BOLD
    ws.cell(
        row=6, column=total_col,
        value=f"=SUM(A6:{get_column_letter(len(active_pillars))}6)",
    ).font = BOLD

    # ---- table geometry
    PILLAR_ROW = 8        # merged pillar band over each block of metric columns
    WEIGHT_ROW = 9        # metric and pillar weights, aligned with their columns
    GROUP_ROW = 10        # pillar grouping labels
    HEAD_ROW = 11         # metric labels
    FIRST = 12            # first submarket row
    last = FIRST + n - 1

    ws.cell(row=WEIGHT_ROW, column=1, value="Weight ->").font = SMALL_GREY
    ws.cell(row=HEAD_ROW, column=1, value="Submarket").font = WHITE_BOLD
    ws.cell(row=HEAD_ROW, column=1).fill = HEADER_FILL
    ws.cell(row=HEAD_ROW, column=2, value="GEOID").font = WHITE_BOLD
    ws.cell(row=HEAD_ROW, column=2).fill = HEADER_FILL

    metric_col: dict[str, int] = {}
    col = 3
    pillar_metric_range: dict[str, tuple[int, int]] = {}
    for pillar in active_pillars:
        keys = [k for k in metric_keys if specs[k]["pillar"] == pillar
                and weights.metrics.get(k, 0) > 0]
        if not keys:
            continue
        start_col = col
        for key in keys:
            metric_col[key] = col
            w = ws.cell(row=WEIGHT_ROW, column=col, value=float(weights.metrics[key]))
            w.fill = EDIT_FILL
            w.border = BOX
            head = ws.cell(row=HEAD_ROW, column=col, value=specs[key]["label"])
            head.fill = HEADER_FILL
            head.font = Font(color="FFFFFF", bold=True, size=9)
            head.alignment = Alignment(wrap_text=True, vertical="bottom")
            arrow = "high good" if specs[key]["higher_is_better"] else "low good"
            g = ws.cell(row=GROUP_ROW, column=col, value=arrow)
            g.font = SMALL_GREY
            g.fill = PILLAR_FILL
            ws.column_dimensions[get_column_letter(col)].width = 13
            col += 1
        pillar_metric_range[pillar] = (start_col, col - 1)
        # The pillar name gets a merged band of its own above the metric
        # columns, so it does not sit on top of the first metric's direction
        # marker and make that column look mislabelled.
        band = ws.cell(row=PILLAR_ROW, column=start_col, value=PILLAR_LABELS[pillar])
        band.font = BOLD
        band.fill = PILLAR_FILL
        band.alignment = Alignment(horizontal="center")
        if col - 1 > start_col:
            ws.merge_cells(start_row=PILLAR_ROW, start_column=start_col,
                           end_row=PILLAR_ROW, end_column=col - 1)

    # pillar score columns
    pillar_score_col: dict[str, int] = {}
    col += 1
    pillar_block_start = col
    for i, pillar in enumerate(active_pillars):
        pillar_score_col[pillar] = col
        head = ws.cell(row=HEAD_ROW, column=col, value=PILLAR_LABELS[pillar] + " score")
        head.fill = HEADER_FILL
        head.font = Font(color="FFFFFF", bold=True, size=9)
        head.alignment = Alignment(wrap_text=True)
        # This weight cell points at the editable pillar block above, so there is
        # exactly one place to change a pillar weight.
        ws.cell(row=WEIGHT_ROW, column=col,
                value=f"={get_column_letter(1 + i)}$6").font = SMALL_GREY
        ws.column_dimensions[get_column_letter(col)].width = 13
        col += 1
    pillar_block_end = col - 1

    total_score_col = col
    coverage_col = col + 1
    sortkey_col = col + 2
    for c, label in ((total_score_col, "TOTAL SCORE"), (coverage_col, "Data coverage"),
                     (sortkey_col, "Sort key")):
        head = ws.cell(row=HEAD_ROW, column=c, value=label)
        head.fill = HEADER_FILL
        head.font = WHITE_BOLD
        head.alignment = Alignment(wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = 14

    # ---- rows
    for i, unit in enumerate(units):
        r = FIRST + i
        ws.cell(row=r, column=1, value=unit["name"]).font = BOLD
        ws.cell(row=r, column=2, value=unit["geoid"])
        raw_row = raw_first + i

        for key, c in metric_col.items():
            rc = get_column_letter(raw_cols[key])
            cell_ref = f"'Raw data'!{rc}{raw_row}"
            col_range = f"'Raw data'!${rc}${raw_first}:${rc}${raw_last}"
            # A scored column can end up with a single number in it, when every
            # other submarket is MISSING. PERCENTRANK.INC then divides by n-1=0
            # and returns an error, and STDEV.P returns 0, which the old formula
            # scored as 50. Both are wrong: a column with one value carries no
            # relative information at all. COUNT guards it, and IFERROR catches
            # anything else so one bad column can never blank the Ranking tab.
            if method == "zscore":
                core = (
                    f"IF(STDEV.P({col_range})=0,50,"
                    f"MAX(0,MIN(100,50+15*({cell_ref}-AVERAGE({col_range}))"
                    f"/STDEV.P({col_range}))))"
                )
            else:
                core = f"PERCENTRANK.INC({col_range},{cell_ref})*100"
            if not specs[key]["higher_is_better"]:
                core = f"100-({core})"
            target = ws.cell(
                row=r, column=c,
                value=f'=IFERROR(IF(AND(ISNUMBER({cell_ref}),COUNT({col_range})>1),'
                      f'{core},""),"")',
            )
            target.number_format = "0.0"
            target.border = BOX

        for pillar, (c0, c1) in pillar_metric_range.items():
            a = f"{get_column_letter(c0)}{r}:{get_column_letter(c1)}{r}"
            w = f"${get_column_letter(c0)}${WEIGHT_ROW}:${get_column_letter(c1)}${WEIGHT_ROW}"
            # SUMPRODUCT treats the empty strings left by a missing metric as
            # zero when the argument is a plain range, so the numerator needs no
            # wrapper. N() would look tidier but N() does not accept an array in
            # Excel and returns #VALUE!, and --ISNUMBER() is not portable across
            # every calculation engine, so ISNUMBER()*1 is used for the divisor.
            # COUNT enforces weights.yml's min_metrics_per_pillar here, so the
            # workbook drops a thin pillar on the same rule the Python scorer
            # uses. Without it the two disagree the moment that setting is
            # raised above 1.
            formula = (
                f'=IF(OR(COUNT({a})<{min_metrics},'
                f'SUMPRODUCT(ISNUMBER({a})*1,{w})=0),"",'
                f"SUMPRODUCT({a},{w})/SUMPRODUCT(ISNUMBER({a})*1,{w}))"
            )
            c = ws.cell(row=r, column=pillar_score_col[pillar], value=formula)
            c.number_format = "0.0"
            c.border = BOX

        pa = f"{get_column_letter(pillar_block_start)}{r}:{get_column_letter(pillar_block_end)}{r}"
        pw = (f"${get_column_letter(pillar_block_start)}${WEIGHT_ROW}:"
              f"${get_column_letter(pillar_block_end)}${WEIGHT_ROW}")
        total = ws.cell(
            row=r, column=total_score_col,
            value=(f'=IF(SUMPRODUCT(ISNUMBER({pa})*1,{pw})=0,"",'
                   f"SUMPRODUCT({pa},{pw})/SUMPRODUCT(ISNUMBER({pa})*1,{pw}))"),
        )
        total.number_format = "0.0"
        total.font = BOLD
        total.border = BOX

        # Coverage: the share of the intended total weight that actually had a
        # number behind it. Shown so a thin row is visibly thin.
        cov_terms = []
        for pillar, (c0, c1) in pillar_metric_range.items():
            a = f"{get_column_letter(c0)}{r}:{get_column_letter(c1)}{r}"
            w = f"${get_column_letter(c0)}${WEIGHT_ROW}:${get_column_letter(c1)}${WEIGHT_ROW}"
            pw_cell = f"{get_column_letter(pillar_score_col[pillar])}${WEIGHT_ROW}"
            score_cell = f"{get_column_letter(pillar_score_col[pillar])}{r}"
            cov_terms.append(
                f'IF({score_cell}="",0,'
                f"{pw_cell}*IFERROR(SUMPRODUCT(ISNUMBER({a})*1,{w})/SUM({w}),0))"
            )
        cov = ws.cell(
            row=r, column=coverage_col,
            value=f"=IFERROR(({'+'.join(cov_terms)})/SUM({pw}),0)" if cov_terms else "=0",
        )
        cov.number_format = "0%"
        cov.border = BOX

        # The sort key does two things. The tiny row-index nudge stops LARGE and
        # MATCH being confused by two submarkets scoring exactly the same. The
        # large penalty pushes any row below the coverage threshold beneath
        # every row we could actually measure, which is the same rule
        # screener/score.py applies, and it is what stops a submarket with one
        # figure out of thirteen taking rank 1 with a score of 100.
        tot_ref = f"{get_column_letter(total_score_col)}{r}"
        cov_ref = f"{get_column_letter(coverage_col)}{r}"
        ws.cell(
            row=r, column=sortkey_col,
            value=f'=IF({tot_ref}="","",{tot_ref}+ROW()/1000000'
                  f"-IF({cov_ref}<{COVERAGE_PENALTY_THRESHOLD},1000,0))",
        ).number_format = "0.000000"

    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 12
    ws.freeze_panes = ws.cell(row=FIRST, column=3)
    ws.row_dimensions[HEAD_ROW].height = 46

    return {
        "sheet": ws.title,
        "first_row": FIRST,
        "last_row": last,
        "total_col": total_score_col,
        "coverage_col": coverage_col,
        "sortkey_col": sortkey_col,
        "pillar_score_col": pillar_score_col,
        "active_pillars": active_pillars,
    }


# ----------------------------------------------------------------- ranking tab
def _write_ranking(wb: Workbook, bundle: dict, layout: dict, explanation: list[str]) -> None:
    ws = wb.create_sheet("Ranking", 0)
    units = bundle["units"]
    n = len(units)
    sheet = f"'{layout['sheet']}'"
    first, last = layout["first_row"], layout["last_row"]
    sk = get_column_letter(layout["sortkey_col"])
    tot = get_column_letter(layout["total_col"])
    cov = get_column_letter(layout["coverage_col"])

    ws["A1"] = f"{bundle['market']['name']}: submarket ranking"
    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"] = (
        f"{n} submarkets screened out of {bundle['in_range_size']} within "
        f"{bundle['market']['max_distance_miles']:.0f} miles of an employment centre "
        f"({bundle['universe_size']} in the trade area in total). "
        f"Built {bundle['built_at']}."
    )
    ws["A2"].font = SMALL_GREY
    ws["A3"] = (
        "This tab is live. Change a weight on the Scoring tab and the order here "
        "changes with it."
    )
    ws["A3"].font = SMALL_GREY

    headers = ["Rank", "Submarket", "Total score"]
    headers += [PILLAR_LABELS[p] for p in layout["active_pillars"]]
    headers += ["Data coverage", "Flag"]
    head_row = 5
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=head_row, column=i, value=h)
        c.fill = HEADER_FILL
        c.font = WHITE_BOLD
        c.alignment = Alignment(wrap_text=True)

    sk_range = f"{sheet}!${sk}${first}:${sk}${last}"
    name_range = f"{sheet}!$A${first}:$A${last}"

    for i in range(n):
        r = head_row + 1 + i
        rank = i + 1
        ws.cell(row=r, column=1, value=rank).font = BOLD
        match = f"MATCH(LARGE({sk_range},{rank}),{sk_range},0)"
        ws.cell(row=r, column=2,
                value=f'=IFERROR(INDEX({name_range},{match}),"")').font = BOLD
        ws.cell(row=r, column=3,
                value=f'=IFERROR(INDEX({sheet}!${tot}${first}:${tot}${last},{match}),"")'
                ).number_format = "0.0"
        for j, pillar in enumerate(layout["active_pillars"]):
            pc = get_column_letter(layout["pillar_score_col"][pillar])
            ws.cell(row=r, column=4 + j,
                    value=f'=IFERROR(INDEX({sheet}!${pc}${first}:${pc}${last},{match}),"")'
                    ).number_format = "0.0"
        cov_col = 4 + len(layout["active_pillars"])
        ws.cell(row=r, column=cov_col,
                value=f'=IFERROR(INDEX({sheet}!${cov}${first}:${cov}${last},{match}),"")'
                ).number_format = "0%"
        cov_cell = f"{get_column_letter(cov_col)}{r}"
        ws.cell(
            row=r, column=cov_col + 1,
            value=f'=IF({cov_cell}="","",'
                  f'IF({cov_cell}<{COVERAGE_PENALTY_THRESHOLD},"thin data",'
                  f'IF(A{r}<=3,"TOP 3","")))',
        ).font = BOLD
        if rank <= 3:
            for c in range(1, cov_col + 2):
                ws.cell(row=r, column=c).fill = TOP3_FILL
        for c in range(1, cov_col + 2):
            ws.cell(row=r, column=c).border = BOX

    note_row = head_row + n + 3
    ws.cell(row=note_row, column=1, value="Why the top submarket ranks first").font = BOLD
    for i, line in enumerate(explanation, start=1):
        c = ws.cell(row=note_row + i, column=1, value=line)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=note_row + i, start_column=1,
                       end_row=note_row + i, end_column=7)
        ws.row_dimensions[note_row + i].height = 30

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 32
    for i in range(3, 3 + len(layout["active_pillars"]) + 3):
        ws.column_dimensions[get_column_letter(i)].width = 14
    ws.freeze_panes = "A6"


# ------------------------------------------------------------------- sources tab
def _write_sources(wb: Workbook, bundle: dict) -> None:
    ws = wb.create_sheet("Sources and gaps")
    specs = bundle["specs"]
    values = bundle["values"]

    ws["A1"] = "Every source used, and everything that is missing"
    ws["A1"].font = Font(bold=True, size=14)

    headers = ["Column", "Metric key", "Pillar", "Scored", "Source", "Vintage",
               "Retrieved", "URL", "Submarkets with data", "Most common gap"]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=3, column=i, value=h)
        c.fill = HEADER_FILL
        c.font = WHITE_BOLD

    r = 4
    for key, spec in specs.items():
        cells = [values.get(u["geoid"], {}).get(key) or {} for u in bundle["units"]]
        have = sum(1 for c in cells if c.get("value") is not None)
        sample = next((c for c in cells if c.get("value") is not None), None) or \
            next((c for c in cells if c.get("source")), {})
        reasons = [c.get("missing_reason", "") for c in cells if c.get("value") is None]
        common = max(set(reasons), key=reasons.count) if reasons else ""
        row = [
            spec["label"], key, PILLAR_LABELS.get(spec["pillar"], spec["pillar"]),
            "yes" if spec["scored"] else "context only",
            sample.get("source", ""), sample.get("vintage", ""),
            sample.get("retrieved_at", ""), sample.get("url", ""),
            f"{have} of {len(cells)}", common,
        ]
        for i, v in enumerate(row, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = BOX
        if have == 0:
            for i in range(1, len(headers) + 1):
                ws.cell(row=r, column=i).fill = MISSING_FILL
        r += 1

    if bundle.get("failures"):
        r += 2
        ws.cell(row=r, column=1, value="Source modules that failed or were skipped").font = BOLD
        for name, msg in bundle["failures"].items():
            r += 1
            ws.cell(row=r, column=1, value=name).font = BOLD
            c = ws.cell(row=r, column=2, value=msg)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=10)

    widths = [34, 26, 16, 12, 30, 28, 20, 44, 18, 44]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A4"


def build_workbook(bundle: dict, weights, explanation: list[str], path: Path) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    raw_cols = _write_raw(wb, bundle)
    layout = _write_scoring(wb, bundle, weights, raw_cols)
    _write_ranking(wb, bundle, layout, explanation)
    _write_sources(wb, bundle)
    wb.properties.title = f"{bundle['market']['name']} submarket screen"
    wb.properties.created = datetime.now(timezone.utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
