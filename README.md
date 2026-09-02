# Senus PLC — AI-Native Board Report

A board reporting platform for **Senus PLC** (Euronext Access Dublin, `SENUS`), built
for the Assiduous Technology Graduate Assessment.

Every figure in the report is extracted from a published source document by an
AI pipeline, loaded into Postgres, computed by deterministic code, and
traceable back to the exact page it came from — with AI-generated commentary
grounded strictly in that same computed data, never in the raw filings.

**Live:** https://senus-board-report-phi.vercel.app
**Repository:** https://github.com/seangavigan00-Obair/senus-board-report (public)
**Demo video:** https://youtu.be/MUXYe-6BUfg

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
        ├──────────────────────────────────┐
        ▼                                  ▼
pipeline/load_db.py          web/          Next.js 16 · React 19 · Tailwind 4
Loads facts, metrics and     ├── the published payload (source of truth for
reconciliation findings          the pack — a board report is a point-in-time
into Postgres (schema.sql)       document, not a live query)
        │                     ├── /api/facts, /api/reconciliation — live
        ▼                         Postgres queries for provenance drill-down
Postgres                      ├── pipeline/commentary.py + /api/ask — AI
Fact-level provenance,            commentary and grounded Q&A, given ONLY the
queryable independently           computed metrics and a management transcript
of the published pack.            excerpt, never the raw filings
```

**Deployed:** https://senus-board-report-phi.vercel.app (the report itself has
no runtime dependency on Postgres — DATABASE_URL is unset in production, and
`/api/health` confirms `{"database": false}` with the pack rendering normally.
Facts-level drill-down beyond the published payload needs a reachable Postgres
instance; locally that is a plain install, in production it would be one
environment variable away, e.g. Neon).

`pipeline/schema.sql` is the Postgres model — dimensional rather than
table-per-statement, because the sources present overlapping line items under
different headings in different orders.

**Provenance is enforced, not conventional.** `source_document` and `source_page`
are `NOT NULL`. A figure nobody can trace cannot be inserted.

### Technologies

Python 3.14 · `anthropic` 1.1 · Pydantic · pypdf · Pillow · PostgreSQL ·
Next.js 16.3 · React 19.2 · TypeScript · Tailwind 4

No charting library. The report has four chart shapes; a 100 kB dependency to
draw polylines and rectangles is weight a board pack doesn't need. Charts are
inline SVG.

### Brand

Colours and typefaces are taken from senus.com's own design tokens rather than
sampled by eye — `#20948B` teal, `#023C28` deep forest green, Figtree for
headings and Mulish for body. The deep green anchors the navigation the way the
site uses it for hero sections.

One deliberate departure: white text on the brand teal measures **3.70:1**, which
fails WCAG AA for normal text. senus.com does this on its buttons. A board report
should not, so `--accent` stays the true brand teal for chart fills (where the
3:1 non-text threshold applies and it passes) and `--accent-strong` (`#17706A`,
5.90:1) carries anything with white text on it. Same hue, same brand, legible.

---

## Three decisions that shape everything

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

### 3. AI commentary is grounded in computed data, never in raw filings

The brief asks for "AI-powered insights, commentary or financial analysis." The
easy wrong answer sends the source PDFs back to an LLM and asks it to analyse
Senus's performance — reintroducing the exact failure mode the rest of this
project exists to prevent, a model doing financial reasoning with no way to
check its arithmetic.

Both AI commentary features — the offline per-audience generator
(`pipeline/commentary.py`) and the live Q&A endpoint (`/api/ask`) — are given
exactly two sources and nothing else:

1. The **computed metrics** `pipeline/metrics.py` already calculated and
   verified. The model narrates numbers Python already produced; it is never
   asked to compute anything.
2. Excerpts of the **timestamped transcript** of management's half-year
   results presentation (extracted from the supplied `Senus PLC YOUTUBE
   VIDEO.docx`) — Brendan Allen and Stephen Coen explaining these numbers in
   their own words. Anything drawn from it must be attributed explicitly to
   management, never stated as independent fact.

Every response returns a `metrics_cited` list, checked server-side against the
metrics actually supplied before the UI renders it — a model citing an id it
invented is a grounding failure and is caught here, not trusted on its say-so.
The Q&A endpoint additionally returns `grounded: false` with an explicit
refusal when a question can't be answered from either source, rather than
filling the gap with general knowledge about Senus or natural capital markets.

Both features degrade honestly when the API key has no credit: a normalised
message states plainly that AI commentary is unavailable and that every other
figure in the report is computed by deterministic code and unaffected — never
a raw stack trace.

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

  pages read  14 across 5 documents
  precision   100.0%   (88 of 88 matched facts correct)
  recall      100.0%   (88 of 88 verified facts found)
    via native_text  44/44 correct
    via vision       44/44 correct
```

**Both extraction paths score perfectly** — 44/44 reading rotated photographs
of audited accounts via vision, 44/44 reading native text. This is the final
run, after the `entity_scope` field (see "The consolidated/company trap"
below) resolved the last class of ambiguity by design rather than by luck of
source precedence.

Recall is scoped to the exact `(document, page)` pairs a run actually read. An
earlier version scoped by period and reported twelve "misses" for facts on pages
the run never opened. A number quoted in a README has to mean something precise.

### What the failures taught

Getting here took two rounds of fixing real bugs, not one clean run.

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
prompt, and a second full re-run scored **100%** with them fixed.

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
- **Testing the deployment, not just the build.** `npm run build` succeeding
  locally proved nothing about a path bug that only exists once code leaves
  the monorepo: `/api/ask` read the management transcript from a directory
  outside Vercel's project root, which is silently excluded from the deployed
  bundle. A local dev server and a passing build both hid it; hitting the
  live URL after deploying did not.
- **Verifying the SDK shape before writing it, not after debugging it.** The
  live Q&A route's first draft used the Python structured-output syntax in a
  TypeScript file — `output_format` as a raw JSON schema, no `output_config`
  nesting. Checking the bundled TypeScript reference before running it caught
  the mismatch immediately, rather than after a confusing runtime error.

Model: `claude-opus-5` throughout, with Pydantic (Python) and Zod (TypeScript)
structured outputs. Full-corpus extraction cost is ~$2.30; commentary
generation for all four audiences is ~$0.05.

---

## Running it

```bash
pip install -r requirements.txt psycopg2-binary python-docx
export ANTHROPIC_API_KEY=sk-ant-...

python -m pipeline.documents          # classify the corpus
python -m pipeline.run --dry-run      # extraction plan + cost estimate
python -m pipeline.run                # extract (51 pages, ~$2.30)
python validation/score.py data/extracted/facts.json
python -m pipeline.metrics            # metric table in the terminal
python -m pipeline.build              # build the report payload

# Postgres (local install, or any hosted instance via DATABASE_URL)
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/senus
python -m pipeline.load_db            # golden set + pipeline extraction, one schema apply

# AI commentary (requires API credit; ~$0.05 for all four audiences)
python -m pipeline.commentary

cd web && npm install && npm run dev
```

`python -m pipeline.build --from-pipeline` builds from the extraction instead of
the golden set. The metrics engine accepts either source through the same
interface, so it is testable against verified ground truth before the pipeline is
trusted anywhere near it.

`pipeline/load_db.py` applies `schema.sql` exactly once and loads both fact
sources into it — calling it twice with different `--golden-only` /
`--pipeline-only` flags would silently destroy the first load, since
`apply_schema` drops and recreates every table. That bug was caught during
development; the fix is loading both sources under one schema application, and
is documented in the module docstring.

---

## Current status and known gaps

**Working:** classification, dual-path extraction, precedence, reconciliation,
metrics engine (100 values across 8 periods), Postgres loader with fact-level
provenance, board report application with sidebar navigation, audience toggle,
revenue and margin charts, a cash-walk waterfall, cost-base composition, a full
period comparison table, click-through provenance on every figure backed by
live Postgres queries, AI commentary and grounded Q&A, and a production
deployment at the URL above. JSON API at `/api/report`, `/api/facts`,
`/api/reconciliation`, `/api/ask`, `/api/health`.

**Resolved during development** (kept here rather than deleted, since the
failure and recovery is itself part of the AI-assisted workflow this README
documents):

- The Anthropic account backing this project ran out of credit twice while
  building the AI commentary and the `entity_scope` re-extraction. Both are
  now complete: commentary is generated for all four audiences and live in
  production, and the re-extraction scored 100% precision/recall (see above).
  Every other figure in the report was unaffected throughout, since it is
  computed by deterministic Python and never depended on either feature.

**Not yet done, and honestly:**

- **Production Postgres is not provisioned.** The schema, loader and live
  drill-down queries are all built and proven against a local instance
  (verified: a click on a figure fetches its corroborating facts live, e.g.
  H1 FY2026 revenue showing the winning statement figure alongside two
  narrative restatements it outranked). Swapping to a hosted instance in
  production is one `DATABASE_URL` environment variable, no code change — the
  report itself does not depend on it being set, confirmed via
  `/api/health` returning `{"database": false}` in production with the pack
  rendering normally.
- No automated test suite beyond the validation harness.
- No login/authentication. The brief asks for something "a CEO would log in to
  and use"; this reads as describing the product's polish and workflow rather
  than requiring real auth for a graded demo, so it was deprioritised in
  favour of the extraction pipeline, database and AI commentary the brief
  names explicitly as the technical focus.

---

## Deliverables

1. **YouTube demo:** https://youtu.be/MUXYe-6BUfg
2. **GitHub repo:** https://github.com/seangavigan00-Obair/senus-board-report
   (public).
3. **One-page write-up:** optional per the brief; produced separately as
   `docs/Senus-Board-Report-Writeup.pdf` (generated by `docs/make_writeup.py`)
   — a one-page cold read for someone deciding whether to open the repo,
   distinct in purpose from this README's engineering depth.

## Repository

```
data/source/          15 published documents + management transcript
pipeline/             documents · extract · schema · select · metrics · build ·
                      run · load_db · commentary
pipeline/schema.sql   Postgres schema (facts, metrics, reconciliation, provenance)
validation/           golden_set.json · check_golden_set.py · score.py
web/                  Next.js application (App Router, API routes, Postgres client)
```
