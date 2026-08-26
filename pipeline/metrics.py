"""
The metrics engine.

Everything here is deterministic Python. No model is involved in any
calculation, and that is the single most important architectural decision in
this project: a language model that quietly gets a margin wrong produces a board
report that is confidently, invisibly false.

Every result carries the formula it used and the facts it consumed, each with
its own provenance, so the UI can show its working. A number a director cannot
trace back to a page of a published document has no business in a board report.

Two pieces of finance judgement are encoded here rather than left to the
frontend:

  NOT MEANINGFUL. Senus is loss-making. ROCE, DSCR and EBITDA margin are all
  arithmetically computable and all economically meaningless when the numerator
  is a loss. Printing "ROCE: -930%" looks like analysis and is noise. These
  return a result flagged `not_meaningful` with the underlying figure retained,
  so the UI can say "n/m" and still show why on request.

  DERIVED PERIODS. Only half-years and full years are published, so second
  halves are derived by subtraction (H2 = FY - H1). That is how the seasonality
  in this business becomes visible - soil sampling is weather-dependent and H1
  FY2026 was hit by a wet winter. Derived periods are marked as such.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

Unit = Literal["eur", "pct", "months", "ratio", "count", "x"]

MONTHS = {"FY2023": 12, "FY2024": 12, "FY2025": 12, "FY2026": 12,
          "HY2025": 6, "HY2026": 6, "H2FY2025": 6, "H2FY2026": 6}

# Ordered oldest to newest. Derived periods sit alongside published ones.
PERIOD_ORDER = ["FY2023", "FY2024", "HY2025", "H2FY2025", "FY2025",
                "HY2026", "H2FY2026", "FY2026"]

# Prior period for year-on-year comparison: like for like, never half against full.
PRIOR_PERIOD = {
    "FY2025": "FY2024", "FY2026": "FY2025",
    "HY2026": "HY2025", "H2FY2026": "H2FY2025",
}


@dataclass(frozen=True)
class FactRef:
    """A fact as consumed by a calculation, with enough to cite it."""

    period: str
    metric: str
    value: float
    source: str
    page: int | str
    is_approximate: bool = False


@dataclass
class MetricResult:
    id: str
    label: str
    period: str
    value: float | None
    unit: Unit
    formula: str
    inputs: list[FactRef] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    note: str | None = None

    @property
    def not_meaningful(self) -> bool:
        return "not_meaningful" in self.flags

    @property
    def is_approximate(self) -> bool:
        return any(i.is_approximate for i in self.inputs) or "approximate" in self.flags

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "period": self.period,
            "value": self.value, "unit": self.unit, "formula": self.formula,
            "flags": self.flags, "note": self.note,
            "not_meaningful": self.not_meaningful,
            "is_approximate": self.is_approximate,
            "inputs": [
                {"period": i.period, "metric": i.metric, "value": i.value,
                 "source": i.source, "page": i.page,
                 "is_approximate": i.is_approximate}
                for i in self.inputs
            ],
        }


class FactStore:
    """
    Read access to facts, keyed by (period, metric).

    Loads either the golden set or a pipeline extraction - both carry period,
    metric, value and provenance, so the metrics engine does not care which it
    is given. That means the whole engine can be tested against hand-verified
    ground truth before the pipeline is trusted.
    """

    def __init__(self, facts: dict[tuple[str, str], FactRef]):
        self._facts = dict(facts)
        self._derive_second_halves()

    @classmethod
    def from_golden_set(cls, path: Path) -> "FactStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        facts = {
            (f["period"], f["metric"]): FactRef(
                f["period"], f["metric"], float(f["value"]),
                f["source"], f["page"],
                f.get("confidence") == "approximate",
            )
            for f in data["facts"]
        }
        return cls(facts)

    @classmethod
    def from_extraction(cls, path: Path) -> "FactStore":
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        facts: dict[tuple[str, str], FactRef] = {}
        for row in rows:
            f, p = row["fact"], row["provenance"]
            key = (f["period"], f["metric"])
            facts.setdefault(key, FactRef(
                f["period"], f["metric"], float(f["value"]),
                p["document"], p["page"], f.get("is_approximate", False),
            ))
        return cls(facts)

    # Flow metrics subtract; stock metrics (balance sheet) do not - a second-half
    # balance sheet is simply the year-end one.
    FLOW_METRICS = {
        "turnover", "cost_of_sales", "gross_profit", "distribution_costs",
        "administrative_expenses", "other_operating_income", "operating_profit",
        "profit_before_tax", "profit_after_tax", "depreciation",
        "cash_flow_from_operations", "cash_flow_from_investing",
        "cash_flow_from_financing",
    }

    def _derive_second_halves(self) -> None:
        for full, first, second in (("FY2025", "HY2025", "H2FY2025"),
                                    ("FY2026", "HY2026", "H2FY2026")):
            for metric in self.FLOW_METRICS:
                whole, half = self._facts.get((full, metric)), self._facts.get((first, metric))
                if whole is None or half is None:
                    continue
                self._facts[(second, metric)] = FactRef(
                    second, metric, whole.value - half.value,
                    f"derived: {full} less {first}",
                    f"{whole.source} p{whole.page}; {half.source} p{half.page}",
                    whole.is_approximate or half.is_approximate,
                )
            # A second half ENDS on the year-end date, so every balance sheet
            # figure at that date is the year-end one. Carrying these across is
            # what lets runway be measured at the latest balance sheet date.
            for (period, metric), ref in list(self._facts.items()):
                if period == full and metric not in self.FLOW_METRICS:
                    self._facts.setdefault((second, metric), FactRef(
                        second, metric, ref.value, ref.source, ref.page,
                        ref.is_approximate,
                    ))

    def get(self, period: str, metric: str) -> FactRef | None:
        return self._facts.get((period, metric))

    def value(self, period: str, metric: str) -> float | None:
        ref = self._facts.get((period, metric))
        return ref.value if ref else None

    def periods(self) -> list[str]:
        present = {p for p, _ in self._facts}
        return [p for p in PERIOD_ORDER if p in present]


# --------------------------------------------------------------------------
# Metric definitions
# --------------------------------------------------------------------------

def _need(store: FactStore, period: str, *metrics: str) -> list[FactRef] | None:
    refs = [store.get(period, m) for m in metrics]
    return None if any(r is None for r in refs) else refs  # type: ignore[return-value]


def revenue(store: FactStore, period: str) -> MetricResult | None:
    refs = _need(store, period, "turnover")
    if not refs:
        return None
    return MetricResult("revenue", "Revenue", period, refs[0].value, "eur",
                        "turnover as reported", refs)


def revenue_growth_yoy(store: FactStore, period: str) -> MetricResult | None:
    prior = PRIOR_PERIOD.get(period)
    if not prior:
        return None
    refs = [store.get(period, "turnover"), store.get(prior, "turnover")]
    if any(r is None for r in refs):
        return None
    current, previous = refs[0].value, refs[1].value  # type: ignore[union-attr]
    if previous == 0:
        return None
    return MetricResult(
        "revenue_growth_yoy", "Revenue growth (YoY)", period,
        (current - previous) / previous * 100, "pct",
        f"({period} turnover - {prior} turnover) / {prior} turnover",
        refs,  # type: ignore[arg-type]
    )


def gross_margin(store: FactStore, period: str) -> MetricResult | None:
    refs = _need(store, period, "gross_profit", "turnover")
    if not refs:
        return None
    gp, rev = refs[0].value, refs[1].value
    if rev == 0:
        return None
    result = MetricResult("gross_margin", "Gross margin", period, gp / rev * 100,
                          "pct", "gross profit / turnover", refs)
    # Defect D01: the HY2025 column does not foot. Management's published margin
    # agrees with the printed gross profit, so we use it and say why.
    cos = store.get(period, "cost_of_sales")
    if cos and abs((rev + cos.value) - gp) > 1:
        result.flags.append("source_inconsistent")
        result.note = (
            f"Source does not foot: turnover EUR {rev:,.0f} less cost of sales "
            f"EUR {abs(cos.value):,.0f} is EUR {rev + cos.value:,.0f}, but gross profit "
            f"is printed as EUR {gp:,.0f}. Margin uses the printed gross profit, which is "
            f"what management's own published commentary is consistent with."
        )
    return result


def operating_margin(store: FactStore, period: str) -> MetricResult | None:
    refs = _need(store, period, "operating_profit", "turnover")
    if not refs:
        return None
    op, rev = refs[0].value, refs[1].value
    if rev == 0:
        return None
    result = MetricResult("operating_margin", "Operating margin", period,
                          op / rev * 100, "pct", "operating profit / turnover", refs)
    if op < 0:
        result.flags.append("loss_making")
    return result


def ebitda(store: FactStore, period: str) -> MetricResult | None:
    op = store.get(period, "operating_profit")
    if op is None:
        return None
    dep = store.get(period, "depreciation")
    inputs = [op] + ([dep] if dep else [])
    result = MetricResult(
        "ebitda", "EBITDA", period, op.value + (dep.value if dep else 0.0), "eur",
        "operating profit + depreciation and amortisation", inputs,
    )
    result.flags.append("derived_non_gaap")
    if dep is None:
        result.flags.append("depreciation_unavailable")
        result.note = ("No depreciation is disclosed for this period, so EBITDA "
                       "equals operating profit and is understated by the "
                       "depreciation charge.")
    if result.value is not None and result.value < 0:
        result.flags.append("loss_making")
    return result


def ebitda_margin(store: FactStore, period: str) -> MetricResult | None:
    e = ebitda(store, period)
    rev = store.get(period, "turnover")
    if e is None or rev is None or rev.value == 0 or e.value is None:
        return None
    result = MetricResult("ebitda_margin", "EBITDA margin", period,
                          e.value / rev.value * 100, "pct",
                          "EBITDA / turnover", e.inputs + [rev])
    if e.value < 0:
        result.flags += ["not_meaningful", "loss_making"]
        result.note = ("EBITDA is negative, so the margin is shown as not "
                       "meaningful. The absolute EBITDA figure and its trend are "
                       "the informative measures while the company is pre-profit.")
    return result


def working_capital(store: FactStore, period: str) -> MetricResult | None:
    refs = _need(store, period, "debtors", "cash_and_cash_equivalents",
                 "creditors_within_one_year")
    if not refs:
        return None
    value = sum(r.value for r in refs)
    result = MetricResult("working_capital", "Working capital", period, value, "eur",
                          "debtors + cash - creditors due within one year", refs)
    # The Loamin earn-out is a current liability but is performance-linked and
    # payable in shares or cash only if targets are met. Including it in working
    # capital would overstate the near-term cash requirement.
    contingent = store.get(period, "contingent_consideration")
    if contingent:
        result.inputs.append(contingent)
        result.flags.append("excludes_contingent_consideration")
        result.note = (
            f"Excludes the EUR {abs(contingent.value):,.0f} Loamin contingent "
            f"consideration, which is performance-linked and payable only if "
            f"targets are met. Including it would take working capital to "
            f"negative EUR {abs(value + contingent.value):,.0f}."
        )
    return result


# Where a period's opening cash comes from - the preceding period's closing
# balance. Used only for the fallback burn calculation below.
OPENING_CASH_FROM = {
    "FY2024": "FY2023", "FY2025": "FY2024",
    "HY2026": "FY2025", "H2FY2026": "HY2026",
}


def monthly_burn(store: FactStore, period: str) -> MetricResult | None:
    """
    Net operating cash burn per month.

    Preferred basis is operating plus investing cash flow, which excludes
    financing and so measures what the business consumes before any fundraising.

    Where no cash flow statement is published - FY2026 has none, only an AGM
    trading update - fall back to the movement in the cash balance. That fallback
    is less clean because a movement includes any financing in the period, so it
    is flagged, and the flag matters: applied to a full year that contained a
    EUR 1.1m raise it would badly understate the burn. It is only sound over a
    window with no financing, which is why it is used for the second half of
    FY2026 rather than the full year.
    """
    months = MONTHS.get(period)
    if not months:
        return None

    refs = _need(store, period, "cash_flow_from_operations", "cash_flow_from_investing")
    if refs:
        result = MetricResult(
            "monthly_burn", "Net monthly cash burn", period,
            sum(r.value for r in refs) / months, "eur",
            f"(cash flow from operations + cash flow from investing) / {months} months",
            refs,
        )
        result.note = ("Excludes financing, so it measures the cash the business "
                       "consumes before any fundraising.")
        return result

    opening_period = OPENING_CASH_FROM.get(period)
    closing = store.get(period, "cash_and_cash_equivalents")
    opening = store.get(opening_period, "cash_and_cash_equivalents") if opening_period else None
    if closing is None or opening is None:
        return None

    result = MetricResult(
        "monthly_burn", "Net monthly cash burn", period,
        (closing.value - opening.value) / months, "eur",
        f"(closing cash - opening cash) / {months} months",
        [closing, opening],
    )
    result.flags.append("derived_from_cash_movement")
    result.note = (
        "No cash flow statement is published for this period, so the burn is "
        "derived from the movement in the cash balance. This includes any "
        "financing in the period; no equity raise was announced between "
        "31 December 2025 and the year end, so it is a fair proxy for "
        "operating burn."
    )
    return result


def cash_runway(store: FactStore, period: str) -> MetricResult | None:
    """Months of cash at the period-end burn rate."""
    cash = store.get(period, "cash_and_cash_equivalents")
    burn = monthly_burn(store, period)
    if cash is None or burn is None or burn.value is None or burn.value >= 0:
        return None
    months = cash.value / abs(burn.value)
    result = MetricResult(
        "cash_runway", "Cash runway", period, months, "months",
        "closing cash / net monthly cash burn", [cash] + burn.inputs,
    )
    if months < 3:
        result.flags.append("critical")
    elif months < 6:
        result.flags.append("warning")
    result.note = ("Assumes the burn rate of this period continues and no further "
                   "capital is raised.")
    return result


def roce(store: FactStore, period: str) -> MetricResult | None:
    op = store.get(period, "operating_profit")
    refs = _need(store, period, "net_assets", "creditors_after_one_year")
    if op is None or not refs:
        return None
    net_assets, long_term = refs
    capital_employed = net_assets.value - long_term.value  # long term is negative
    if capital_employed == 0:
        return None
    result = MetricResult(
        "roce", "Return on capital employed", period,
        op.value / capital_employed * 100, "pct",
        "operating profit / (net assets + long-term creditors)",
        [op, net_assets, long_term],
    )
    if op.value < 0 or capital_employed < 0:
        result.flags += ["not_meaningful", "loss_making"]
        result.note = ("ROCE is not meaningful for a loss-making company. Shown "
                       "for completeness; the Board should read the absolute "
                       "operating loss and its trend instead.")
    return result


def debt_service_coverage(store: FactStore, period: str) -> MetricResult | None:
    e = ebitda(store, period)
    interest = store.get(period, "interest_payable")
    repayment = store.get(period, "loan_repayment")
    if e is None or e.value is None or interest is None:
        return None
    service = abs(interest.value) + abs(repayment.value if repayment else 0.0)
    if service == 0:
        return None
    inputs = e.inputs + [interest] + ([repayment] if repayment else [])
    result = MetricResult(
        "dscr", "Debt service coverage ratio", period, e.value / service, "x",
        "EBITDA / (interest paid + principal repayments)", inputs,
    )
    if e.value < 0:
        result.flags += ["not_meaningful", "loss_making"]
        result.note = ("EBITDA is negative, so there is no earnings coverage of "
                       "debt service. Debt is currently serviced from cash "
                       "reserves and equity funding, not from operations - which "
                       "is the material point for a credit provider.")
    return result


def cost_ratio(metric: str, label: str) -> Callable[[FactStore, str], MetricResult | None]:
    def compute(store: FactStore, period: str) -> MetricResult | None:
        refs = _need(store, period, metric, "turnover")
        if not refs:
            return None
        cost, rev = refs[0].value, refs[1].value
        if rev == 0:
            return None
        return MetricResult(f"{metric}_ratio", label, period,
                            abs(cost) / rev * 100, "pct",
                            f"{metric.replace('_', ' ')} / turnover", refs)
    return compute


REGISTRY: dict[str, Callable[[FactStore, str], MetricResult | None]] = {
    "revenue": revenue,
    "revenue_growth_yoy": revenue_growth_yoy,
    "gross_margin": gross_margin,
    "operating_margin": operating_margin,
    "ebitda": ebitda,
    "ebitda_margin": ebitda_margin,
    "admin_cost_ratio": cost_ratio("administrative_expenses",
                                   "Administrative costs as % of revenue"),
    "working_capital": working_capital,
    "monthly_burn": monthly_burn,
    "cash_runway": cash_runway,
    "roce": roce,
    "dscr": debt_service_coverage,
}


def compute_all(store: FactStore) -> list[MetricResult]:
    out: list[MetricResult] = []
    for period in store.periods():
        for compute in REGISTRY.values():
            result = compute(store, period)
            if result is not None:
                out.append(result)
    return out


def _format(result: MetricResult) -> str:
    if result.not_meaningful:
        return "n/m"
    v = result.value
    if v is None:
        return "-"
    return {
        "eur": f"{v:>14,.0f}",
        "pct": f"{v:>13.1f}%",
        "months": f"{v:>11.1f} mo",
        "x": f"{v:>13.2f}x",
    }.get(result.unit, f"{v:>14,.2f}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    store = FactStore.from_golden_set(root / "validation" / "golden_set.json")
    results = compute_all(store)

    by_metric: dict[str, dict[str, MetricResult]] = {}
    for r in results:
        by_metric.setdefault(r.id, {})[r.period] = r

    periods = store.periods()
    print(f"\n{'metric':<38}" + "".join(f"{p:>17}" for p in periods))
    print("-" * (38 + 17 * len(periods)))
    for metric_id, per_period in by_metric.items():
        label = next(iter(per_period.values())).label
        row = f"{label[:37]:<38}"
        for p in periods:
            r = per_period.get(p)
            row += f"{_format(r) if r else '-':>17}" if r else f"{'-':>17}"
        print(row)

    flagged = [r for r in results if r.flags and r.note]
    print(f"\n{len(results)} metric values computed across {len(periods)} periods.")
    print(f"{len([r for r in results if r.not_meaningful])} suppressed as not meaningful.\n")
    for r in sorted(flagged, key=lambda x: (x.id, x.period))[:6]:
        print(f"  {r.id} / {r.period}: {r.note[:150]}")
    print()
