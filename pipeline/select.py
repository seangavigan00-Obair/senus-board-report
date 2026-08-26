"""
Choosing between competing facts for the same (period, metric).

The corpus states the same figure more than once, at different precisions. The
half-year results announcement opens with a Highlights section reading "Group
Revenue up 4.1% to EUR 354.8k" and then, four pages later, prints the actual
profit and loss account: "Turnover 354,813".

Both are correct. Only one belongs in a board report.

The first extraction run got this wrong in a way worth recording, because the
model did not: the pipeline extracted BOTH figures faithfully and the loader then
kept whichever it met first, which was the rounded one. Precision looked like a
model problem and was a data-modelling problem.

Precedence, most authoritative first:

  1. A primary financial statement - profit and loss, balance sheet, cash flow.
     These are the figures the directors approved and the auditors saw.
  2. A KPI disclosure. Real figures, but often operational rather than statutory.
  3. Narrative text. Accurate, and routinely rounded to one decimal place.

Within a tier, an exact figure beats a hedged one ("almost EUR 1.0 million"),
and an audited source beats an unaudited one.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, TypeVar

STATEMENT_PRECEDENCE = {
    "profit_and_loss": 0,
    "balance_sheet": 0,
    "cash_flow": 0,
    "kpi": 1,
    "narrative": 2,
    "none": 3,
}

# Audited documents outrank unaudited ones stating the same figure.
AUDITED_DOCUMENTS = {
    "ADF-Farm-Solutions-Consolidated-Financial-Statements-30-June-2025.pdf",
}

# A board report covers the GROUP. Parent-company-only figures are real and
# audited but answer a different question, so they rank below consolidated ones
# and never displace them. See EntityScope in schema.py.
SCOPE_PRECEDENCE = {"consolidated": 0, "not_stated": 1, "company": 2}

T = TypeVar("T")


def authority(
    statement: str,
    is_approximate: bool,
    document: str = "",
    entity_scope: str = "not_stated",
) -> tuple[int, int, int, int]:
    """Sort key: lower is more authoritative."""
    return (
        SCOPE_PRECEDENCE.get(entity_scope, 1),
        STATEMENT_PRECEDENCE.get(statement, 3),
        1 if is_approximate else 0,
        0 if document in AUDITED_DOCUMENTS else 1,
    )


def choose(candidates: Iterable[T], key: Callable[[T], tuple[int, int, int]]) -> T:
    return min(candidates, key=key)


def collapse(
    rows: Iterable[dict[str, Any]],
    *,
    period: Callable[[dict], str],
    metric: Callable[[dict], str],
    statement: Callable[[dict], str],
    approximate: Callable[[dict], bool],
    document: Callable[[dict], str],
    value: Callable[[dict], float],
    scope: Callable[[dict], str] = lambda r: r.get("entity_scope", "not_stated"),
) -> tuple[dict[tuple[str, str], dict], list[dict]]:
    """
    Collapse many facts to one per (period, metric), applying precedence.

    Returns the winners and a list of superseded facts. The superseded list is
    not waste - it is shown in the UI as corroboration ("also stated as EUR 354.8k
    in the Highlights"), and a genuine disagreement between two statement-tier
    sources is a reconciliation finding, not a tie to be broken quietly.
    """
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        grouped.setdefault((period(row), metric(row)), []).append(row)

    winners: dict[tuple[str, str], dict] = {}
    superseded: list[dict] = []

    def rank(row: dict) -> tuple[int, int, int, int]:
        return authority(statement(row), approximate(row), document(row), scope(row))

    for key, group in grouped.items():
        ranked = sorted(group, key=rank)
        best, rest = ranked[0], ranked[1:]
        winners[key] = best
        best_rank = rank(best)

        for other in rest:
            entry = dict(other)
            entry["_superseded_by"] = value(best)
            # A conflict is only interesting when two sources of EQUAL authority
            # disagree. A consolidated figure differing from the parent-company
            # one is expected, not a defect; so is a statement differing from a
            # rounded narrative restatement of it.
            entry["_conflict"] = (
                rank(other)[:2] == best_rank[:2]
                and abs(value(other) - value(best)) > 1
            )
            superseded.append(entry)

    return winners, superseded
