# Demo video script

Target length: **6–8 minutes**. Screen recording + voiceover, one continuous take
if possible — a script this specific is easier to deliver live than to edit
around. Timings are guides, not a stopwatch requirement.

Have open before you start recording:
- The live app: https://senus-board-report-phi.vercel.app
- A terminal in the repo root, ready to run two commands
- `pipeline/metrics.py` and `pipeline/schema.py` open in an editor, scrolled to
  the relevant spot (see cues below)

---

## 0:00–0:40 — Open on the problem, not the product

Don't open on the dashboard. Open on why this was hard.

> "This is a board report for Senus PLC, an Irish company on Euronext Access.
> The brief asks for an AI-native platform that turns their published
> financials into a board pack. The obvious way to build that is to hand an
> LLM the PDFs and ask it to write a report. I didn't do that, and the reason
> why is the whole point of this project."

Show the source corpus briefly (`data/source/` in a file explorer or `ls`).

> "Fifteen published documents. Some are normal text PDFs. But the audited
> FY2025 accounts — the only source for full-year figures — are a scanned
> photograph of a printed document, rotated 90 degrees, with zero machine-
> readable text. There is no path to these numbers that doesn't go through a
> vision model."

## 0:40–2:00 — The extraction pipeline

Switch to terminal.

```bash
python -m pipeline.documents
```

> "This classifies every document by how much real text it has. [point at the
> output] Native text PDFs average over a thousand characters a page. The
> scanned ones average zero. That split decides which extraction path each
> page takes — and it's measured, not assumed, so if a document ever gets
> replaced the pipeline re-routes itself."

```bash
python validation/check_golden_set.py
```

> "Before I wrote a line of extraction code, I hand-transcribed 88 figures
> from these documents and built a checker that proves they actually
> articulate — the P&L foots, the balance sheet balances. [point at output]
> One thing didn't pass: it's flagged, not hidden."

**Beat: the D01 defect.** This is the strongest moment in the whole demo —
slow down here.

> "That flag is a real footing error in Senus's own published half-year
> results. Turnover minus cost of sales doesn't equal the printed gross
> profit — it's off by exactly one thousand euro. I checked it three ways:
> management's own growth percentage only works against the printed figure,
> their published margin only works against the printed figure, and the
> current-year column on the same page foots perfectly. Cost of sales is the
> likely typo. My pipeline records both figures exactly as printed and flags
> the contradiction — it never silently corrects a published document."

```bash
python validation/score.py data/extracted/facts.json
```

> "That's the accuracy of the AI extraction against my hand-verified ground
> truth: 100% precision, 100% recall, across every page — including the
> vision path reading that rotated scan."

## 2:00–3:00 — The database

> "Extraction into a database is what the brief actually asks for, so it's
> not optional here."

```bash
psql -U postgres -d senus -c "SELECT period_id, metric, entity_scope, value, source_document, source_page FROM facts WHERE period_id='FY2025' AND metric='profit_after_tax';"
```

> "This is a real finding the database caught: Irish statutory accounts print
> the group AND the parent company separately, with genuinely different
> numbers. €590,256 consolidated, €593,571 company-only. My schema tags every
> fact with which one it is, so the board report can't accidentally mix
> group and parent figures — which would be a material error in a real
> board pack."

## 3:00–5:00 — The board report itself

Switch to the browser, live site.

> "This is the actual application. It opens on the thing a board most needs
> to see."

Point at the liquidity alert.

> "Cash fell from seven hundred thirty-five thousand euro to about a hundred
> and thirty thousand in six months. That's 1.3 months of runway, computed
> from published figures, not asserted."

Toggle the audience switcher (Board → Credit → Equity).

> "Same data, reframed for who's reading it. A credit provider needs
> coverage and runway. An equity investor needs growth against the company's
> own fifty-percent CAGR target."

Click into a chart (e.g. Revenue by half) and point at the H1/H2 split.

> "This is a finding the derived-period logic surfaced on its own. The
> half-year results reported 4.1% growth and it reads like a slowdown. Split
> the year properly and H1 was hit by a wet winter delaying soil sampling —
> H2 grew 30.1%. The full-year number hides both halves."

Click a figure to open the provenance panel.

> "Every number is clickable. This shows the formula, the exact source
> document and page, and — because it's wired to Postgres — any other figure
> the corpus stated for the same line item, ranked by which source is more
> authoritative."

## 5:00–6:30 — The AI layer, and why it doesn't hallucinate

> "The brief asks for AI-powered insights. The wrong way to do that is to
> hand the raw filings back to an LLM and ask it to analyse the company —
> that reintroduces the exact problem this whole project exists to prevent:
> a model doing financial reasoning with no way to check its arithmetic."

Scroll to the AI Commentary card.

> "So this model sees exactly two things: the metrics my code already
> calculated and verified, and an excerpt of management's own results
> presentation transcript. It's never given the raw PDFs, and it's never
> asked to compute anything — only to narrate numbers that already exist."

Click a citation chip.

> "Every citation is checked against what the model was actually given
> before it ever reaches the screen — if it invented a metric id, that would
> be caught here, not trusted."

Type a question into "Ask about this report" — use a real one live.

> "This is a live, grounded question — not scripted."

Then type a question outside scope (e.g. share price).

> "And when a question falls outside what these two sources can answer, it
> says so, rather than guessing."

## 6:30–7:30 — Close: architecture and what I'd do next

Show the architecture diagram from the README, or just say it.

> "End to end: PDFs classified and routed, extracted by Claude Opus 5 with
> structured outputs, reconciled against itself, loaded into Postgres,
> computed by deterministic Python — never an LLM — and served through
> Next.js with full provenance. Deployed and live at the URL in the
> description."

> "If I had another week: hosted Postgres in production instead of local,
> and a broader golden set covering the AGM circular and the leadership
> transition disclosure, which I didn't have time to hand-verify."

Cut.

---

## Things to say out loud that a transcript alone won't carry

- **State the accuracy number verbally**, don't just show it on screen —
  graders skim transcripts.
- **Name the D01 defect explicitly as "a mistake in Senus's own published
  accounts that my reconciliation layer caught"** — this is the single
  highest-value sentence in the video.
- **Say "the model never calculates" out loud at least once** — it's the
  architectural thesis of the whole project and it needs to be spoken, not
  just visible in a code comment.

## If you're short on time, cut in this order

1. Cut the "what I'd do next" close first.
2. Cut the second Q&A example (the refusal) — keep only the working one.
3. Never cut: the D01 defect, the accuracy number, the consolidated/company
   database finding, "the model never calculates."
