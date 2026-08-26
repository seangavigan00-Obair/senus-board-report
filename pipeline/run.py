"""
Pipeline entry point.

The manifest below is deliberate rather than "every page of everything". The
corpus contains 200+ pages, most of which are the Memorandum and Articles of
Association, proxy forms and boilerplate carrying no financial substance. Sending
them to a vision model would cost real money to extract nothing. Each entry
records WHY those pages are in scope, so the selection is reviewable.

Run:  python -m pipeline.run              extract the manifest
      python -m pipeline.run --dry-run    show the plan and estimated cost
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import anthropic

from .documents import DocKind, classify, load_pages, SOURCE_DIR
from .extract import extract_page, write
from .schema import StoredFact

OUT = Path(__file__).resolve().parent.parent / "data" / "extracted" / "facts.json"

# Claude Opus 5, USD per million tokens.
PRICE_IN, PRICE_OUT = 5.00, 25.00


@dataclass(frozen=True)
class Target:
    document: str
    pages: list[int] | None  # None means every page
    reason: str


MANIFEST = [
    Target(
        "ADF-Farm-Solutions-Consolidated-Financial-Statements-30-June-2025.pdf",
        None,
        "Audited FY2025 statutory accounts. The only source for full FY2024 and "
        "FY2025 line items. Scanned throughout, so every page goes via vision. "
        "The notes carry depreciation and the fixed asset movements, which the "
        "summary table in the Information Document omits.",
    ),
    Target(
        "Senus_HalfYearResultsDec2025_PR_V19032026-FINAL-clean.pdf",
        list(range(1, 10)),
        "HY2026 interim statements with HY2025 comparatives - P&L, balance "
        "sheet and cash flow. Also the source of the customer account count.",
    ),
    Target(
        "Senus-PLC-Information-Document-December-2025.pdf",
        [25, 26, 27],
        "Section 7 operating and financial review: the summary financial table "
        "(the only source of FY2024/FY2025 cash flow splits and the FY2023 "
        "closing cash balance) and the KPI section with enterprise customer "
        "counts and ACV by product line.",
    ),
    Target(
        "Senus_PR_AGMStatement_V08072026.pdf",
        [1, 2],
        "The only published FY2026 figures - revenue, year-end cash, channel "
        "and geography mix, and the annualised cost reduction. All directors' "
        "indications rather than audited, and flagged approximate.",
    ),
    Target(
        "Senus-Limited-Company-Balance-Sheet-as-at-8-December-2025.pdf",
        None,
        "Pre-listing balance sheet at 8 December 2025. Bridges FY2025 year end "
        "to the HY2026 interim position and covers the re-registration as a plc.",
    ),
]


def plan() -> list[tuple[Target, DocKind, list[int]]]:
    rows = []
    for target in MANIFEST:
        path = SOURCE_DIR / target.document
        if not path.exists():
            print(f"  MISSING: {target.document}")
            continue
        kind, _ = classify(path)
        pages = target.pages or [p.page_number for p in load_pages(path)]
        rows.append((target, kind, pages))
    return rows


def main() -> int:
    rows = plan()
    total_pages = sum(len(pages) for _, _, pages in rows)
    vision_pages = sum(len(p) for _, k, p in rows if k is DocKind.SCANNED)

    print(f"\nExtraction plan - {total_pages} pages "
          f"({vision_pages} vision, {total_pages - vision_pages} native text)\n")
    for target, kind, pages in rows:
        print(f"  {target.document[:66]:<68} {kind.value:<8} {len(pages):>3} pages")

    if "--dry-run" in sys.argv:
        # A scanned page costs roughly 1.6k input tokens; a native page of dense
        # text roughly 1.2k. Output runs about 1.5k per page of statements.
        est_in = vision_pages * 1_600 + (total_pages - vision_pages) * 1_200
        est_out = total_pages * 1_500
        cost = est_in / 1e6 * PRICE_IN + est_out / 1e6 * PRICE_OUT
        print(f"\n  rough estimate: ~{est_in:,} input + ~{est_out:,} output "
              f"tokens, about ${cost:.2f}\n")
        return 0

    client = anthropic.Anthropic()
    facts: list[StoredFact] = []
    tokens_in = tokens_out = 0

    for target, _, pages in rows:
        print(f"\n{target.document}")
        for page in load_pages(SOURCE_DIR / target.document, pages):
            page_facts = extract_page(page, client)
            facts.extend(page_facts)
            print(f"  p{page.page_number:<3} {page.kind.value:<8} {len(page_facts):>3} facts")

    write(facts, OUT)
    if tokens_in:
        print(f"  cost ~${tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
