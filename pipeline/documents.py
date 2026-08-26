"""
Corpus registry and page loading.

The Senus source documents split into two populations that need completely
different extraction paths:

  NATIVE  - a real text layer. pypdf returns thousands of characters per page.
  SCANNED - one full-page JPEG per page and no text layer at all. pypdf returns
            about 11 characters per page, which is just the page furniture.

Classification is measured, not assumed: `classify()` reads the document and
decides. That way, if a document is ever replaced with a different scan, the
pipeline re-routes itself instead of silently producing empty extractions.

The scanned pages in this corpus were photographed in landscape while the PDF
page box is portrait, so the image content sits at 90 degrees to the page. The
PDF carries no /Rotate key - the rotation lives in a content-stream transform
we do not want to parse - so we normalise geometrically: if the page box is
portrait and the image is landscape, rotate it upright.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from pypdf import PdfReader
from PIL import Image

SOURCE_DIR = Path(__file__).resolve().parent.parent / "data" / "source"

# Below this many characters per page, a PDF has no usable text layer.
# The corpus is strongly bimodal - scanned documents sit at ~11 chars/page and
# native ones at 3,000+ - so the exact threshold is not load-bearing.
TEXT_LAYER_THRESHOLD = 100

# Scanned pages are photographed sideways. Positive angles rotate
# counter-clockwise in Pillow. Verified visually against ADF page 10: -90
# produces portrait but upside down, so the correct correction is +90.
LANDSCAPE_CORRECTION_DEGREES = 90


class DocKind(str, Enum):
    NATIVE = "native"
    SCANNED = "scanned"


@dataclass(frozen=True)
class Page:
    """One page of one document, carrying enough provenance to cite it."""

    document: str
    page_number: int  # 1-indexed, matches what a reader sees
    kind: DocKind
    text: str | None = None
    image: Image.Image | None = None

    @property
    def citation(self) -> str:
        return f"{self.document} p{self.page_number}"


def _normalise_orientation(image: Image.Image, page_is_portrait: bool) -> Image.Image:
    """Rotate a sideways scan upright. See module docstring."""
    image_is_landscape = image.width > image.height
    if page_is_portrait and image_is_landscape:
        return image.rotate(LANDSCAPE_CORRECTION_DEGREES, expand=True)
    return image


def classify(pdf_path: Path) -> tuple[DocKind, float]:
    """Return the document kind and its measured characters-per-page."""
    reader = PdfReader(pdf_path)
    total = sum(len(page.extract_text() or "") for page in reader.pages)
    per_page = total / max(len(reader.pages), 1)
    kind = DocKind.NATIVE if per_page >= TEXT_LAYER_THRESHOLD else DocKind.SCANNED
    return kind, per_page


def load_pages(pdf_path: Path, pages: list[int] | None = None) -> list[Page]:
    """
    Load pages ready for extraction.

    `pages` is a list of 1-indexed page numbers; None means every page.
    Native pages come back with text, scanned pages with an upright image.
    """
    pdf_path = Path(pdf_path)
    kind, _ = classify(pdf_path)
    reader = PdfReader(pdf_path)
    wanted = pages or range(1, len(reader.pages) + 1)

    out: list[Page] = []
    for number in wanted:
        page = reader.pages[number - 1]

        if kind is DocKind.NATIVE:
            out.append(Page(pdf_path.name, number, kind, text=page.extract_text() or ""))
            continue

        embedded = list(page.images)
        if not embedded:
            # A scanned document with a page that carries no image at all -
            # blank separator sheets do this. Record it rather than crashing,
            # so the run reports a gap instead of losing a page silently.
            out.append(Page(pdf_path.name, number, kind, text=""))
            continue

        image = Image.open(io.BytesIO(embedded[0].data))
        image.load()
        portrait = page.mediabox.height >= page.mediabox.width
        out.append(Page(pdf_path.name, number, kind,
                        image=_normalise_orientation(image, portrait)))

    return out


def corpus() -> list[tuple[str, DocKind, int, float]]:
    """Every source document with its kind, page count and text density."""
    rows = []
    for pdf in sorted(SOURCE_DIR.glob("*.pdf")):
        kind, density = classify(pdf)
        rows.append((pdf.name, kind, len(PdfReader(pdf).pages), density))
    return rows


if __name__ == "__main__":
    print(f"\n{'document':<70} {'kind':<8} {'pages':>5} {'chars/page':>11}")
    print("-" * 97)
    for name, kind, pages, density in corpus():
        print(f"{name[:69]:<70} {kind.value:<8} {pages:>5} {density:>11,.0f}")
    print()
