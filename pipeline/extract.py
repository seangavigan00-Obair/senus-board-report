"""
Dual-path extraction: native text pages and scanned image pages converge on one
schema.

Both paths use the same system prompt and the same Pydantic output schema. Only
the content block differs - a text block or an image block. That is deliberate:
it means a figure extracted from a scan and a figure extracted from a text PDF
are indistinguishable downstream except for the `extraction_path` recorded in
provenance, so the reconciliation layer can cross-check one against the other.

The model is never asked to compute anything. It reads figures off a page. Every
derived number in this project - margins, growth, EBITDA, runway - is computed by
deterministic Python in the metrics layer, because an arithmetic slip inside a
board report is worse than no board report.
"""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from PIL import Image

from .documents import DocKind, Page, load_pages, SOURCE_DIR
from .schema import PageExtraction, PERIOD_IDS, Provenance, StoredFact

MODEL = "claude-opus-5"
MAX_TOKENS = 16000

# Senus reports to a 30 June year end. Column headings in the source documents
# say "2025" or "31-Dec-25", so the model needs the mapping spelled out or it
# will invent period labels.
SYSTEM_PROMPT = f"""You extract financial figures from the statutory accounts and \
regulatory announcements of Senus PLC, an Irish company listed on Euronext Access \
Dublin. Senus was called ADF Farm Solutions Limited before 10 December 2025 - \
treat both names as the same reporting entity.

The financial year ends 30 June. Map column headings to these period ids:

  FY2023  year ended 30 June 2023
  FY2024  year ended 30 June 2024   (headed "2024")
  FY2025  year ended 30 June 2025   (headed "2025")
  HY2025  six months ended 31 December 2024  (headed "31-Dec-24")
  HY2026  six months ended 31 December 2025  (headed "31-Dec-25")
  FY2026  year ended 30 June 2026

Note the half-year trap: the six months ended 31 December 2025 falls in financial \
year 2026, so it is HY2026 and its comparative is HY2025. Use only the period ids \
listed above: {', '.join(PERIOD_IDS)}.

Rules:

1. Read figures. Never calculate one. If a page shows turnover and cost of sales \
but no gross profit, extract two facts, not three. Deriving the third is another \
system's job.

2. Extract every column, not just the current period. Statements print a \
comparative column and it is a real period with real figures.

3. Normalise signs. Costs, expenses, liabilities and cash outflows are negative. \
Income, assets and cash inflows are positive. Published statements are \
inconsistent about brackets - some print "Cost of sales 64,861" as a positive \
number that is plainly a deduction. Record what the figure MEANS in \
`value`, and what the page PRINTS in `value_as_printed`.

   Two exceptions, because they are effects rather than costs:
   - Depreciation and amortisation appearing as an ADD-BACK in a cash flow \
statement are POSITIVE. They increase cash relative to the loss.
   - A cost REDUCTION or saving is POSITIVE. "We took out EUR 0.4m of costs" is \
a benefit of 400,000, not a cost of -400,000.

3a. Record the entity scope of every figure. Irish statutory accounts print the \
group and the parent company separately with different numbers, and a board \
report covers the group. Read the statement heading: a heading beginning \
"CONSOLIDATED" is `consolidated`; a heading beginning "COMPANY" is `company`. \
Where a document draws no group/company distinction, use `not_stated`. Getting \
this wrong silently mixes group and parent figures in one series.

4. Record figures exactly as printed. Do not correct an apparent error, and do \
not silently reconcile two figures that disagree. If a page contradicts itself, \
extract what is printed and describe the contradiction in `note`. Surfacing an \
inconsistency is valuable; hiding one is a defect.

5. Flag hedged figures. "almost EUR 1.0 million", "approximately", "in excess of" \
and "more than" all mean `is_approximate` is true.

6. Map to the canonical vocabulary or do not map at all. If a line item has no \
good match, put its label in `unmapped_line_items`. A wrong mapping is worse \
than an honest gap.

7. On scanned pages, if a digit is genuinely ambiguous, name the line item in \
`legibility_concerns`. Do not guess quietly."""

USER_INSTRUCTION = (
    "Extract every financial figure on this page into the schema. "
    "If the page carries no financial figures, return statement_type 'none' "
    "and an empty facts list."
)


def _image_block(image: Image.Image) -> dict:
    """Encode a page image, downscaling only if it exceeds the API's limit."""
    # The API accepts images up to 8000px on a side; these scans are ~2338px, so
    # no downscale is needed in practice. The guard keeps the pipeline correct if
    # a higher-resolution scan is ever dropped into the corpus.
    if max(image.size) > 8000:
        image = image.copy()
        image.thumbnail((8000, 8000), Image.LANCZOS)

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=90)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(buffer.getvalue()).decode("ascii"),
        },
    }


def extract_page(page: Page, client: anthropic.Anthropic | None = None) -> list[StoredFact]:
    """Extract one page. Routes to the text or vision path by page kind."""
    client = client or anthropic.Anthropic()

    if page.kind is DocKind.NATIVE:
        content = [{"type": "text", "text": f"<page>\n{page.text}\n</page>"},
                   {"type": "text", "text": USER_INSTRUCTION}]
        path = "native_text"
    else:
        if page.image is None:
            return []
        content = [_image_block(page.image), {"type": "text", "text": USER_INSTRUCTION}]
        path = "vision"

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=PageExtraction,
    )

    extraction: PageExtraction = response.parsed_output
    provenance = Provenance(
        document=page.document,
        page=page.page_number,
        extraction_path=path,
        model=MODEL,
        extracted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    if extraction.unmapped_line_items or extraction.legibility_concerns:
        print(f"    note {page.citation}: "
              f"{len(extraction.unmapped_line_items)} unmapped, "
              f"{len(extraction.legibility_concerns)} legibility concerns")

    return [StoredFact(fact=fact, provenance=provenance) for fact in extraction.facts]


def extract_document(document: str, pages: list[int] | None = None) -> list[StoredFact]:
    """Extract selected pages of one document."""
    client = anthropic.Anthropic()
    loaded = load_pages(SOURCE_DIR / document, pages)
    out: list[StoredFact] = []
    for page in loaded:
        facts = extract_page(page, client)
        print(f"  {page.citation:<78} {page.kind.value:<8} {len(facts):>3} facts")
        out.extend(facts)
    return out


def write(facts: list[StoredFact], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(f.model_dump_json()) for f in facts]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n  wrote {len(facts)} facts to {path}")
