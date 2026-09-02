"""
Builds the one-page write-up as a PDF, per the (optional) brief deliverable.

Deliberately reportlab/Platypus rather than converting the README: the README
is a living engineering document meant to be read in a repo; this is a single
page meant to be read cold, in under two minutes, by someone deciding whether
to open the repo at all. Different job, different density.

Run: python docs/make_writeup.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors

BRAND_DEEP = colors.HexColor("#023C28")
BRAND_TEAL = colors.HexColor("#17706A")
MUTED = colors.HexColor("#5A6B64")
NEGATIVE = colors.HexColor("#B3352B")

OUT = "docs/Senus-Board-Report-Writeup.pdf"

styles = getSampleStyleSheet()

title_style = ParagraphStyle("TitleX", parent=styles["Title"], fontName="Helvetica-Bold",
                              fontSize=17, leading=20, textColor=BRAND_DEEP, spaceAfter=1)
subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Helvetica",
                                 fontSize=9.5, textColor=MUTED, spaceAfter=8)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                     fontSize=10.5, leading=13, textColor=BRAND_DEEP,
                     spaceBefore=8, spaceAfter=3)
body = ParagraphStyle("Body", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=9, leading=12.2, alignment=TA_LEFT, spaceAfter=3)
bullet = ParagraphStyle("Bullet", parent=body, leftIndent=10, bulletIndent=0, spaceAfter=2.5)
metric_num = ParagraphStyle("MetricNum", parent=styles["Normal"], fontName="Helvetica-Bold",
                             fontSize=15, leading=17, textColor=BRAND_TEAL, alignment=1)
metric_num_neg = ParagraphStyle("MetricNumNeg", parent=metric_num, textColor=NEGATIVE)
metric_label = ParagraphStyle("MetricLabel", parent=styles["Normal"], fontName="Helvetica",
                               fontSize=7, leading=8.5, textColor=MUTED, alignment=1)
link_style = ParagraphStyle("Link", parent=body, fontSize=8.5, textColor=BRAND_TEAL)

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    topMargin=14 * mm, bottomMargin=12 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
)

story = []

story.append(Paragraph("Senus PLC — AI-Native Board Report", title_style))
story.append(Paragraph(
    "Assiduous Technology Graduate Assessment · Sean Gavigan", subtitle_style))
story.append(HRFlowable(width="100%", thickness=1, color=BRAND_DEEP, spaceAfter=8))

# Headline metrics row
metrics_data = [[
    Paragraph("100% / 100%", metric_num), Paragraph("1.3 mo", metric_num_neg),
    Paragraph("100", metric_num), Paragraph("3", metric_num),
], [
    Paragraph("extraction precision / recall<br/>vision path: 44/44", metric_label),
    Paragraph("cash runway at 30 Jun 2026<br/>the board-level finding", metric_label),
    Paragraph("deterministic metrics computed<br/>zero calculated by the AI", metric_label),
    Paragraph("source-document defects found<br/>by automated reconciliation", metric_label),
]]
t = Table(metrics_data, colWidths=[42 * mm] * 4)
t.setStyle(TableStyle([
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, 0), 2), ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
    ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white),
]))
story.append(t)
story.append(Spacer(1, 6))

story.append(Paragraph("What this is", h2))
story.append(Paragraph(
    "A board reporting platform for Senus PLC (Euronext Access Dublin, SENUS) built from "
    "15 published source documents. An AI pipeline extracts every financial figure with "
    "page-level provenance into Postgres; every board-facing number is then computed by "
    "deterministic Python, never by the model; and AI-generated commentary and live Q&amp;A "
    "are grounded strictly in that computed data and a management transcript, never in "
    "the raw filings.", body))

story.append(Paragraph("The core engineering problem", h2))
story.append(Paragraph(
    "The audited FY2025 accounts — the only source for full-year figures — are a scanned, "
    "90°-rotated photograph with zero machine-readable text. Other documents are normal "
    "text PDFs. The pipeline measures each document's text density and routes it down a "
    "vision or text extraction path accordingly, converging on one schema so a figure read "
    "from a photograph is indistinguishable downstream from one read from text.", body))

story.append(Paragraph("Three decisions that shape the system", h2))
for txt in [
    "<b>The model reads, code calculates.</b> Every margin, growth rate, EBITDA and "
    "runway figure is deterministic Python with its formula stored beside the result. "
    "An LLM silently miscalculating inside a board report is the failure mode this "
    "architecture exists to prevent.",
    "<b>“Not meaningful” is a first-class result.</b> Senus is loss-making, so ROCE, "
    "DSCR and EBITDA margin are computable and economically meaningless. Twelve values "
    "render as n/m with the reasoning retained, rather than printing a number that looks "
    "like analysis and is noise.",
    "<b>AI commentary is grounded in two sources only</b> — the already-computed metrics "
    "and management's own results-presentation transcript, never the raw filings. Every "
    "citation the model makes is checked server-side against what it was actually given "
    "before the UI renders it.",
]:
    story.append(Paragraph(f"&bull;&nbsp; {txt}", bullet))

story.append(Paragraph("How outputs were validated", h2))
story.append(Paragraph(
    "88 facts were hand-transcribed from source documents before any pipeline code "
    "existed, and a self-consistency checker proves that ground truth articulates "
    "(P&amp;L foots, balance sheet balances). The extraction pipeline scores 100% "
    "precision and recall against it. Along the way, reconciliation caught a genuine "
    "€1,000 footing error in Senus's own published half-year results (turnover less "
    "cost of sales does not equal the printed gross profit) and a consolidated-vs-parent-"
    "company ambiguity in the statutory accounts — both are recorded exactly as printed "
    "and surfaced in the report, never silently corrected.", body))

story.append(Paragraph("Stack &amp; deployment", h2))
story.append(Paragraph(
    "Python (pypdf, Pillow, Pydantic) for extraction and metrics · PostgreSQL for fact-"
    "level provenance · Next.js 16 / React 19 / TypeScript / Tailwind for the application "
    "· Claude Opus 5 with structured outputs throughout. Deployed to Vercel; the published "
    "report renders from a versioned, content-hashed payload with no runtime dependency on "
    "the database, confirmed live.", body))

story.append(Paragraph("Links", h2))
story.append(Paragraph(
    'Live app: <link href="https://senus-board-report-phi.vercel.app" color="#17706A">'
    'senus-board-report-phi.vercel.app</link> &nbsp;&bull;&nbsp; '
    'Repository: <link href="https://github.com/seangavigan00-Obair/senus-board-report" '
    'color="#17706A">github.com/seangavigan00-Obair/senus-board-report</link> (private — '
    "access on request) &nbsp;&bull;&nbsp; Full README covers architecture, validation "
    "methodology, assumptions and AI-assisted workflow in depth.", link_style))

doc.build(story)
print(f"wrote {OUT}")
