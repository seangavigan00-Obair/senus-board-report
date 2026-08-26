"""
Build the board report payload.

This is the seam between the Python side (extraction, reconciliation, metrics)
and the TypeScript side (API routes, UI). It emits one versioned JSON document
containing everything the report needs: periods, metric values with their
formulas and provenance, the reconciliation findings, and the data gaps.

Why a build step rather than the UI querying Postgres per request: the report is
a point-in-time board pack. Directors need the same numbers to be on screen in
January that were on screen when the pack was approved in September, and the
build id is what makes that reproducible. The database remains the system of
record and powers drill-down; this payload is the published pack.

Run:  python -m pipeline.build                 build from the golden set
      python -m pipeline.build --from-pipeline build from the extraction
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .metrics import (
    FactStore, MONTHS, PERIOD_ORDER, compute_all,
)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "validation" / "golden_set.json"
EXTRACTED = ROOT / "data" / "extracted" / "facts.json"
OUT = ROOT / "web" / "public" / "board-report.json"

PERIOD_META = {
    "FY2023": ("annual", "2022-07-01", "2023-06-30", False, False),
    "FY2024": ("annual", "2023-07-01", "2024-06-30", True, False),
    "FY2025": ("annual", "2024-07-01", "2025-06-30", True, False),
    "FY2026": ("annual", "2025-07-01", "2026-06-30", False, False),
    "HY2025": ("half_year", "2024-07-01", "2024-12-31", False, False),
    "HY2026": ("half_year", "2025-07-01", "2025-12-31", False, False),
    "H2FY2025": ("half_year", "2025-01-01", "2025-06-30", False, True),
    "H2FY2026": ("half_year", "2026-01-01", "2026-06-30", False, True),
}

PERIOD_LABEL = {
    "FY2023": "FY2023", "FY2024": "FY2024", "FY2025": "FY2025", "FY2026": "FY2026",
    "HY2025": "H1 FY2025", "HY2026": "H1 FY2026",
    "H2FY2025": "H2 FY2025", "H2FY2026": "H2 FY2026",
}

# Which metrics belong in which board-report section, and which audiences care.
# A credit provider opens the pack for runway and coverage; an equity investor
# opens it for growth against the Senus 2030 target. Same facts, different lead.
SECTIONS = [
    {
        "id": "growth",
        "title": "Growth & Revenue",
        "metrics": ["revenue", "revenue_growth_yoy"],
        "audiences": ["management", "board", "equity", "credit"],
    },
    {
        "id": "profitability",
        "title": "Profitability",
        "metrics": ["gross_margin", "operating_margin", "ebitda", "ebitda_margin",
                    "admin_cost_ratio"],
        "audiences": ["management", "board", "equity"],
    },
    {
        "id": "liquidity",
        "title": "Cash & Liquidity",
        "metrics": ["cash_runway", "monthly_burn", "working_capital"],
        "audiences": ["management", "board", "equity", "credit"],
    },
    {
        "id": "solvency",
        "title": "Solvency & Leverage",
        "metrics": ["dscr"],
        "audiences": ["board", "credit"],
    },
    {
        "id": "returns",
        "title": "Returns",
        "metrics": ["roce"],
        "audiences": ["board", "equity"],
    },
]

# The metric each audience should see first when the report opens.
AUDIENCE_HEADLINE = {
    "management": "monthly_burn",
    "board": "cash_runway",
    "equity": "revenue_growth_yoy",
    "credit": "cash_runway",
}


def build(from_pipeline: bool = False) -> dict:
    source_path = EXTRACTED if from_pipeline else GOLDEN
    if not source_path.exists():
        raise SystemExit(f"no fact source at {source_path}")

    store = (FactStore.from_extraction(source_path) if from_pipeline
             else FactStore.from_golden_set(source_path))
    results = compute_all(store)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    periods = []
    for pid in [p for p in PERIOD_ORDER if p in store.periods()]:
        kind, starts, ends, audited, derived = PERIOD_META[pid]
        periods.append({
            "id": pid, "label": PERIOD_LABEL[pid], "type": kind,
            "starts_on": starts, "ends_on": ends, "months": MONTHS.get(pid),
            "is_audited": audited, "is_derived": derived,
            "basis": ("Derived by subtraction: full year less first half. No "
                      "second-half figures are published separately."
                      if derived else None),
        })

    metrics = [r.to_dict() for r in results]

    payload = {
        "build": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fact_source": "pipeline_extraction" if from_pipeline else "golden_set",
            "fact_source_file": source_path.name,
            "metric_count": len(metrics),
            "period_count": len(periods),
        },
        "entity": golden["entity"],
        "currency": golden["currency"],
        "periods": periods,
        "sections": SECTIONS,
        "audience_headline": AUDIENCE_HEADLINE,
        "metrics": metrics,
        "source_defects": golden.get("known_defects_in_source_documents", []),
        "data_gaps": golden.get("known_data_gaps", []),
        "strategy": {
            "name": "Senus 2030",
            "revenue_cagr_target_pct": 50.0,
            "baseline_period": "FY2025",
            "baseline_revenue": 836991,
            "target_period": "FY2030",
            "ebitda_positive_target": "FY2028",
            "enterprise_customers_target": 100,
            "acv_target": 50000,
            "ireland_revenue_share_target_pct": 50.0,
            "source": "Senus-PLC-Information-Document-December-2025.pdf p26-27",
        },
    }

    # A content hash over the substance (not the timestamp) so a rebuild that
    # changes nothing is visibly identical.
    substance = json.dumps(
        {k: v for k, v in payload.items() if k != "build"},
        sort_keys=True,
    ).encode()
    payload["build"]["content_hash"] = hashlib.sha256(substance).hexdigest()[:16]
    return payload


def main() -> int:
    payload = build(from_pipeline="--from-pipeline" in sys.argv)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    b = payload["build"]
    print(f"\n  board report built from {b['fact_source']}")
    print(f"  {b['metric_count']} metric values across {b['period_count']} periods")
    print(f"  {len(payload['source_defects'])} source defects, "
          f"{len(payload['data_gaps'])} documented data gaps")
    print(f"  content hash {b['content_hash']}")
    print(f"  -> {OUT.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
