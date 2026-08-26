# Senus PLC — AI-Native Board Report

A board reporting platform for **Senus PLC** (Euronext Access Dublin, `SENUS`), built
for the Assiduous Technology Graduate Assessment.

Every figure in the report is extracted from a published source document by an
AI pipeline, computed by deterministic code, and traceable back to the exact page
it came from.

---

## The problem, and what makes it hard

Senus publishes its financials across fifteen documents. They are not uniform:

| | Documents | Text layer | Extraction path |
|---|---|---|---|
| **Native** | Information Document (53pp), 8 press releases and circulars | 1,400–3,400 chars/page | Text → structured output |
| **Scanned** | FY2025 audited accounts (23pp), pre-listing balance sheet (14pp), Memo & Arts (76pp), corporate deck (14pp) | **0 chars/page** | Vision model |

The FY2025 statutory accounts — the only source of full-year line items — are a
**photograph of a printed document, rotated 90°**, with no text layer at all.
Section 3 of the Information Document doesn't reproduce those statements; it
points at them as appendices. So there is no path to the numbers that does not
go through a vision model.

That is the core of this project. The dashboard is the visible half.

---

## Architecture

```
data/source/*.pdf            15 published documents (32 MB), committed for reproducibility
        │
        ▼
pipeline/documents.py        Measures chars/page → routes native vs scanned.
                             Extracts one embedded JPEG per scanned page and
                             rotates it upright. No poppler/Ghostscript needed.
        │
        ▼
pipeline/extract.py          Dual-path extraction. Text pages and image pages use
                             the SAME system prompt and the SAME Pydantic schema —
                             only the content block differs. Claude Opus 5 with
                             structured outputs (`client.messages.parse`).
        │
        ▼
pipeline/schema.py           Closed 39-metric vocabulary. The model maps to it or
                             reports the label as unmapped; it cannot invent one.
                             Every fact carries entity scope + provenance.
        │
        ▼
pipeline/select.py           Source precedence: primary statement > KPI disclosure
                             > narrative. Consolidated > parent-company.
        │
        ▼
pipeline/metrics.py          Deterministic calculation engine. No model involved.
                             Every result stores its formula and its inputs.
        │
        ▼
pipeline/build.py            Versioned board-report payload, content-hashed.
        │
        ▼
web/                         Next.js 16 · React 19 · Tailwind 4 · TypeScript
                             Server-rendered board pack, audience toggle,
                             click-through provenance on every figure.
```

`pipeline/schema.sql` is the Postgres model — dimensional rather than
table-per-statement, because the sources present overlapping line items under
different headings in different orders.

**Provenance is enforced, not conventional.** `source_document` and `source_page`
are `NOT NULL`. A figure nobody can trace cannot be inserted.

### Technologies

Python 3.14 · `anthropic` 1.1 · Pydantic · pypdf · Pillow · PostgreSQL ·
Next.js 16.3 · React 19.2 · TypeScript · Tailwind 4

No charting library. The report has five metric shapes; a 100 kB dependency to
draw a polyline is weight a board pack doesn't need. Charts are inline SVG.

---

## Two decisions that shape everything

### 1. The model reads. It never calculates.

The system prompt is explicit: *"If a page shows turnover and cost of sales but
no gross profit, extract two facts, not three."*

Every derived figure — margins, growth, EBITDA, runway, DSCR, ROCE — is computed
in `pipeline/metrics.py` in plain Python, with the formula string stored
alongside the result. A language model that quietly gets a margin wrong produces
a board report that is confidently and invisibly false. That is the failure mode
this design exists to prevent.

### 2. "Not meaningful" is a first-class concept.

Senus is loss-making. ROCE, DSCR and EBITDA margin are all arithmetically
computable and all economically meaningless when the numerator is a loss.
Twelve values render as `n/m`, with the reasoning retained and shown on click:

> EBITDA is negative, so there is no earnings coverage of debt service. Debt is
> currently serviced from cash reserves and equity funding, not from operations —
> which is the material point for a credit provider.

Printing "ROCE: −930%" looks like analysis. It is noise.

---

## How the outputs were validated

### The golden set

Before any pipeline code existed, **88 facts across 5 periods were transcribed by
hand** from the source documents, each recording its document, page and
statement. `validation/check_golden_set.py` then proves the ground truth
articulates — that the P&L foots, the balance sheet balances, the cash flow ties:

```
$ python validation/check_golden_set.py
18 passed, 0 failed, 1 source-document defect flagged, 0 skipped
```

If the ground truth is wrong, every accuracy figure quoted below is meaningless.

### Extraction accuracy

```
$ python validation/score.py data/extracted/facts.json

  pages read  13 across 4 documents
  precision    96.6%   (85 of 88 matched facts correct)
  recall       96.6%   (85 of 88 verified facts found)
    via native_text  41/44 correct
    via vision       44/44 correct
```

**The vision path — reading rotated photographs of audited accounts — scored
44/44.** Every error was on the native-text path.

Recall is scoped to the exact `(document, page)` pairs a run actually read. An
earlier version scoped by period and reported twelve "misses" for facts on pages
the run never opened. A number quoted in a README has to mean something precise.

### What the failures taught

The first run scored **85.2%**, and 11 of the 13 errors were a single bug — mine,
not the model's.

The half-year announcement states each figure twice: page 1 says *"Group Revenue
up 4.1% to €354.8k"*; page 5 prints the P&L, *"Turnover 354,813"*. The pipeline
extracted **both, correctly**. The loader kept whichever it met first — the
rounded one.

Precision looked like a model problem and was a data-modelling problem. Fixing it
with a real precedence rule (`pipeline/select.py`) moved 85.2% → 96.6%.

The remaining three were sign-convention judgement calls the model made
defensibly — depreciation as a cash-flow *add-back* (an inflow, not a cost) and a
cost *reduction* (a benefit, not a negative cost). Both are now specified in the
prompt.

---

## What the reconciliation layer found

### D01 — a published statement that does not foot

The HY2025 comparative column of the consolidated P&L does not articulate:

```
turnover 340,931  −  cost of sales 69,600  =  271,331
gross profit as printed:                       272,331     ← €1,000 difference
```

Three independent checks say turnover and gross profit are right and **cost of
sales is the typo**:

- Management state growth of **6.5%**. Against 272,331 that's 6.47% ✓; against 271,331, 6.86% ✗
- Management state an HY25 margin of **79.8%**. 272,331/340,931 = 79.88% ✓; 271,331 gives 79.59% ✗
- The HY2026 current-year column foots perfectly, so it is isolated to the comparative

€68,600 would make the column balance exactly, and €69,600 is suspiciously round.

**The pipeline records both figures exactly as printed and flags the
inconsistency. It never silently corrects.** The defect is surfaced in the report
itself, under "Source document defects", because a board pack that hides a
contradiction in its own sources is worse than one that shows it.

`D02` — goodwill is €669,550 on the HY26 balance sheet and €669,500 in note 4
(the balance sheet figure wins; it's the one that makes net assets articulate).
`D03` — several statements tie only to the nearest euro, so reconciliation
tolerance is €1 and €1 differences are never reported to a board.

### The consolidated/company trap

Irish statutory accounts print the **group** and the **parent company**
separately, with different numbers:

| FY2025 | Consolidated (p13) | Company (p14) |
|---|---|---|
| Loss for the year | (590,256) | (593,571) |
| Tangible assets | 48,788 | 48,579 |

The first schema had no way to tell them apart. It got the right answer **by
luck** — precedence happened to favour the consolidated pages. Mixing group and
parent figures into one series would be a material error in a board report.

Every fact now carries `entity_scope`, read off the statement heading, enforced
by a database constraint, and ranked in precedence. A consolidated-vs-company
difference is correctly classified as *expected*, not as a defect.

---

## Assumptions

Stated explicitly because several materially affect the figures.

1. **No monthly data exists in any source document.** The brief asks for
   month-on-month; it cannot be derived honestly from this corpus. Rather than
   fabricate a monthly series, the report derives **second halves by subtraction**
   (H2 = FY − H1), which is defensible and turns out to be the most revealing view
   in the dataset. Derived periods are labelled as derived.
2. **FY2026 is unaudited.** Full-year results are due 11 September 2026. Every
   FY2026 figure comes from the 8 July AGM Statement and is a directors'
   indication — "almost €1.0 million", "approximately €0.13 million". These are
   flagged `approximate` throughout the UI.
3. **FY2026 burn is derived from the cash movement**, since no cash flow
   statement is published. That includes any financing in the period, so it is
   applied only to H2 FY2026, where no raise occurred. Applied to the full year —
   which contained a €1.1m raise — it would understate burn by an order of
   magnitude. The constraint is documented at the calculation.
4. **EBITDA is disclosed nowhere** and is derived as operating profit plus
   depreciation and amortisation, flagged as a non-GAAP measure. Depreciation is
   published only for HY2025/HY2026, so FY EBITDA is understated by the
   depreciation charge and says so.
5. **The Loamin contingent consideration (€850,000) is excluded from working
   capital**, being performance-linked. The note states what including it would do.
6. **FY2023 has only a closing cash balance**, inferred from the FY2024 opening
   balance. No FY2023 P&L or balance sheet exists in the corpus.

The report surfaces all six to the reader under *"What this report cannot tell
you"*. A board pack should say what it does not know.

---

## AI-assisted development workflow

Built with Claude Code (Claude Opus 5) in a pairing loop rather than by prompt-
and-accept:

- **Corpus reconnaissance.** The IR site is a JS app with no direct PDF links;
  the document manifest was located in the release `site.json`, which is how the
  scanned appendices were found at all.
- **Empirical over inferred.** The page-rotation fix was wrong first time (−90°
  produced portrait but upside down). Rather than reason about PDF content-stream
  transforms, I rendered it, looked, and corrected to +90°. The reason is in a
  comment next to the constant.
- **Failures drove the design.** The precedence rule and `entity_scope` both came
  from reading the scorer's error output, not from planning. The scorer's own
  scoping bug was found the same way.
- **AI for extraction, code for arithmetic.** The division of labour is the
  central architectural decision, not an implementation detail.

Model: `claude-opus-5` throughout, with Pydantic structured outputs. Full-corpus
extraction cost is ~$2.30.

---

## Running it

```bash
pip install anthropic pypdf pillow pydantic
export ANTHROPIC_API_KEY=sk-ant-...

python -m pipeline.documents          # classify the corpus
python -m pipeline.run --dry-run      # extraction plan + cost estimate
python -m pipeline.run                # extract (51 pages, ~$2.30)
python validation/score.py data/extracted/facts.json
python -m pipeline.metrics            # metric table in the terminal
python -m pipeline.build              # build the report payload

cd web && npm install && npm run dev
```

`python -m pipeline.build --from-pipeline` builds from the extraction instead of
the golden set. The metrics engine accepts either source through the same
interface, so it is testable against verified ground truth before the pipeline is
trusted anywhere near it.

---

## Current status and known gaps

**Working:** classification, dual-path extraction, precedence, reconciliation,
metrics engine, board report UI with provenance drill-down, JSON API.

**Not yet done, and honestly:**

- The `entity_scope` re-extraction is **incomplete** — the run stopped at page 29
  of 51 when the API account ran out of credit. The committed `facts.json` is
  from the previous run (96.6%, without `entity_scope`). The schema, prompt and
  precedence rule are all in place; it needs one clean run to repopulate.
- **Postgres is modelled but not deployed.** `schema.sql` is written; the loader
  and a hosted instance are outstanding. The UI currently reads the built payload,
  which is the correct source for a point-in-time board pack regardless — but
  drill-down beyond the pack should hit the database.
- **The AI commentary layer is designed, not built.** The intended grounding
  corpus is the timestamped transcript of the Investor Meet Company results
  presentation — management explaining these numbers in their own words — with
  commentary generated strictly from computed metrics, never from raw PDFs.
- No automated test suite beyond the validation harness.

---

## Repository

```
data/source/          15 published documents
pipeline/             documents · extract · schema · select · metrics · build · run
validation/           golden_set.json · check_golden_set.py · score.py
web/                  Next.js application
```
