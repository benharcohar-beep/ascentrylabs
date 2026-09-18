"""Excel and the recalculation engine disagree about ties. Excel is right.

This nearly caused a correct workbook to be broken. The first verification run
against real data reported that every ranking total disagreed with the Python
scorer, and the obvious reading was that the workbook formulas were wrong. They
were not. The `formulas` package, which is used only as an independent oracle
in tests and in `screener.cli verify`, does not implement PERCENTRANK.INC the
way Excel does when values are tied.

Real data ties constantly: every municipality that permitted no multifamily
over the window sits at zero together. So this is not an edge case, it is the
normal state of a permits column.

These tests pin which behaviour is Excel's, so that a future reader who sees
the verification output does not "fix" score.py to match the oracle.
"""
from __future__ import annotations

import pytest

from screener.score import percentrank_inc

# Three tied zeros, as a permits column looks in a real market.
TIED = [0.0, 0.0, 0.0, 12.5, 30.0, 45.7]


def test_excel_ranks_a_tie_at_its_lowest_position():
    """PERCENTRANK.INC finds the first match, so tied values all score the
    rank of the lowest one. Three zeros at the bottom of six values score 0,
    not 20."""
    assert percentrank_inc(TIED, 0.0) == 0.0


def test_the_untied_values_are_unaffected():
    """The disagreement is confined to ties. If the untied values moved too,
    the cause would be something else and this explanation would be wrong."""
    assert percentrank_inc(TIED, 12.5) == 60.0
    assert percentrank_inc(TIED, 30.0) == 80.0
    assert percentrank_inc(TIED, 45.7) == 100.0


def test_the_documented_two_value_tie_case():
    """{10, 10, 30, 40}: Excel gives 0 for 10. A mid-rank convention gives
    0.166. This is the example cited in test_pipeline_end_to_end."""
    assert percentrank_inc([10.0, 10.0, 30.0, 40.0], 10.0) == 0.0


def test_a_tie_at_the_top_still_scores_the_top():
    """Ties at the top rank at the lowest tied position too, which for the
    maximum is still the maximum only if every tied entry is the maximum."""
    assert percentrank_inc([10.0, 20.0, 30.0, 30.0], 30.0) == pytest.approx(66.6, abs=0.1)


def test_every_value_tied_gives_zero_not_fifty():
    """A column where nothing varies carries no information. Scoring it 50
    across the board would quietly add a neutral contribution to every total
    and change the ranking through the weight normalisation."""
    assert percentrank_inc([5.0, 5.0, 5.0], 5.0) == 0.0


# ---------------------------------------------------------------------------
# The oracle itself, proven to differ. Skipped when the package is absent,
# because it is a development dependency.
# ---------------------------------------------------------------------------
formulas = pytest.importorskip("formulas", reason="pip install formulas")


def test_the_oracle_really_does_disagree_and_in_which_direction(tmp_path):
    """Pins the discrepancy rather than describing it.

    The direction matters: the engine reads tied rows HIGHER, so it inflates
    every total that includes a tied column. That is why the verification run
    showed the workbook above Python on every single row, which looked like a
    systematic workbook bug and was not.
    """
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "S"
    for i, value in enumerate(TIED, start=1):
        sheet.cell(row=i, column=1, value=value)
        sheet.cell(row=i, column=2,
                   value=f"=PERCENTRANK.INC($A$1:$A${len(TIED)},A{i})*100")
    path = tmp_path / "ties.xlsx"
    workbook.save(path)

    model = formulas.ExcelModel().loads(str(path)).finish()
    cells = {k.upper(): v for k, v in model.calculate().items()}

    def value_at(row: int):
        cell = cells.get(f"'[{path.name.upper()}]S'!B{row}")
        try:
            return cell.value[0, 0]
        except (AttributeError, IndexError, TypeError):
            return cell

    engine_tied = float(value_at(1))
    ours_tied = percentrank_inc(TIED, 0.0)

    assert engine_tied > ours_tied, (
        "the engine is expected to read a tie higher than Excel does; if this "
        "fails the package has changed and cli verify's explanation is stale"
    )
    assert ours_tied == 0.0
    assert engine_tied == pytest.approx(20.0)

    # Untied values must agree, or the disagreement is not about ties at all.
    assert float(value_at(4)) == pytest.approx(percentrank_inc(TIED, 12.5))
    assert float(value_at(6)) == pytest.approx(percentrank_inc(TIED, 45.7))
