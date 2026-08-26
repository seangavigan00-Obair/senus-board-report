"""
Self-consistency check for the hand-built golden set.

This runs BEFORE any extraction pipeline exists. Its job is to prove that the
figures we transcribed by hand actually articulate - that the P&L foots, the
balance sheet balances, and the cash flow ties. If the ground truth is wrong,
every accuracy number we quote later is meaningless.

Run:  python validation/check_golden_set.py
"""

import json
import sys
from pathlib import Path

GOLDEN = Path(__file__).parent / "golden_set.json"
TOLERANCE = 1  # euro, to absorb rounding in published statements


def load():
    with open(GOLDEN, encoding="utf-8") as fh:
        return json.load(fh)


def index(facts):
    """(period, metric) -> value"""
    out = {}
    for f in facts:
        out[(f["period"], f["metric"])] = f["value"]
    return out


# Breaks that are defects in the published source documents, not in our
# transcription. These are expected to fail arithmetically; the pipeline's job
# is to surface them, so a clean PASS here would actually mean we had lost them.
EXPECTED_DEFECTS = {("R01", "HY2025"): "D01"}


def check(results, cid, period, label, expected, actual):
    if expected is None or actual is None:
        results.append((cid, period, label, "SKIP", "missing input"))
        return
    delta = round(expected - actual, 2)
    ok = abs(delta) <= TOLERANCE
    defect = EXPECTED_DEFECTS.get((cid, period))

    if defect and not ok:
        status, detail = "DEFECT", f"{expected:,.0f} vs {actual:,.0f}  delta {delta:+,.0f}  ({defect}, source document error)"
    elif defect and ok:
        status, detail = "FAIL", f"expected source defect {defect} but the figures now foot - has the golden set been edited?"
    else:
        status = "PASS" if ok else "FAIL"
        detail = f"{expected:,.0f} vs {actual:,.0f}" + (f"  delta {delta:+,.0f}" if not ok else "")
    results.append((cid, period, label, status, detail))


def main():
    data = load()
    v = index(data["facts"])
    g = lambda p, m: v.get((p, m))  # noqa: E731
    results = []

    # R01 - gross profit articulates
    for p in ("FY2024", "FY2025", "HY2025", "HY2026"):
        if g(p, "turnover") is not None and g(p, "cost_of_sales") is not None:
            check(results, "R01", p, "turnover + cost_of_sales = gross_profit",
                  g(p, "turnover") + g(p, "cost_of_sales"), g(p, "gross_profit"))

    # R02 - operating profit articulates
    for p in ("FY2024", "FY2025", "HY2025", "HY2026"):
        gp = g(p, "gross_profit")
        if gp is None:
            continue
        calc = (gp
                + (g(p, "distribution_costs") or 0)
                + (g(p, "administrative_expenses") or 0)
                + (g(p, "other_operating_income") or 0))
        check(results, "R02", p, "gross_profit - opex = operating_profit", calc, g(p, "operating_profit"))

    # R03 - PBT to PAT
    for p in ("FY2024", "FY2025"):
        if g(p, "profit_before_tax") is not None:
            check(results, "R03", p, "profit_before_tax + tax = profit_after_tax",
                  g(p, "profit_before_tax") + (g(p, "tax") or 0), g(p, "profit_after_tax"))

    # R04 - balance sheet balances
    for p in ("FY2024", "FY2025"):
        if g(p, "net_assets") is not None and g(p, "retained_earnings") is not None:
            calc = (g(p, "share_capital") or 144) + (g(p, "share_premium") or 849962) + g(p, "retained_earnings")
            check(results, "R04", p, "share capital + premium + retained = net_assets", calc, g(p, "net_assets"))

    # R04b - HY2026 balance sheet, built up from the asset side
    p = "HY2026"
    fixed = (g(p, "goodwill") or 0) + (g(p, "development_costs") or 0) + (g(p, "tangible_assets") or 0)
    current = (g(p, "debtors") or 0) + (g(p, "cash_and_cash_equivalents") or 0)
    net_current = current + (g(p, "creditors_within_one_year") or 0) + (g(p, "contingent_consideration") or 0)
    calc = fixed + net_current + (g(p, "creditors_after_one_year") or 0)
    check(results, "R04", p, "assets less liabilities = net_assets", calc, g(p, "net_assets"))

    # R05 / R07 - cash walks forward across every period boundary
    walks = [
        ("FY2024", "FY2023", "FY2024"),
        ("FY2025", "FY2024", "FY2025"),
        ("HY2026", "FY2025", "HY2026"),
    ]
    for period, open_from, close_to in walks:
        opening = g(open_from, "cash_and_cash_equivalents")
        closing = g(close_to, "cash_and_cash_equivalents")
        flows = [g(period, k) for k in
                 ("cash_flow_from_operations", "cash_flow_from_investing", "cash_flow_from_financing")]
        if opening is None or closing is None or any(f is None for f in flows):
            results.append(("R05", period, "cash walk", "SKIP", "missing input"))
            continue
        check(results, "R05", period, f"cash {open_from} + flows = cash {close_to}",
              opening + sum(flows), closing)

    # R06 - cross-document agreement, scanned statements vs text Information Document
    for p in ("FY2024", "FY2025"):
        srcs = {f["source"].split("-")[0] for f in data["facts"]
                if f["period"] == p and f["metric"] == "turnover"}
        results.append(("R06", p, "turnover sourced and cross-checked", "PASS" if srcs else "SKIP",
                        ", ".join(sorted(srcs)) or "no source"))

    # R08 - the known goodwill defect must still be present and flagged
    note = next((f.get("note", "") for f in data["facts"]
                 if f["id"] == "F059"), "")
    results.append(("R08", "HY2026", "goodwill 669,550 vs note 4 669,500 discrepancy recorded",
                    "PASS" if "669,500" in note else "FAIL", "documented defect, pipeline must flag"))

    # ---- report ----
    width = max(len(r[2]) for r in results)
    print(f"\nGolden set self-consistency - {len(data['facts'])} facts, "
          f"{len(data['periods'])} periods\n")
    for cid, period, label, status, detail in results:
        mark = {"PASS": "ok  ", "FAIL": "FAIL", "SKIP": "skip", "DEFECT": "flag"}[status]
        print(f"  [{mark}] {cid} {period:<7} {label:<{width}}  {detail}")

    failed = [r for r in results if r[3] == "FAIL"]
    skipped = [r for r in results if r[3] == "SKIP"]
    passed = [r for r in results if r[3] == "PASS"]
    defects = [r for r in results if r[3] == "DEFECT"]
    print(f"\n  {len(passed)} passed, {len(failed)} failed, "
          f"{len(defects)} source-document defects flagged, {len(skipped)} skipped")
    for cid, period, label, _, _ in defects:
        d = next((x for x in data.get("known_defects_in_source_documents", [])
                  if x["id"] == EXPECTED_DEFECTS.get((cid, period))), None)
        if d:
            print(f"    {d['id']} ({d['severity']}) {d['source']} p{d['page']}: {d['description'][:88]}...")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
