-- Board report data model.
--
-- The shape is dimensional rather than a table-per-statement, because the
-- source documents do not agree on presentation: the FY2025 statutory accounts,
-- the Information Document summary and the HY2026 interim statements all print
-- overlapping line items in different orders under different headings. Modelling
-- facts rather than statements is what lets ADF-era and Senus-era figures sit in
-- one series.
--
-- Three rules the schema enforces rather than trusts:
--   1. No fact exists without provenance. `source_document` and `source_page`
--      are NOT NULL - a figure nobody can trace is not admissible.
--   2. Figures as printed are kept alongside sign-normalised values, so the UI
--      can show a director exactly what the page said.
--   3. Metric results store the formula and the facts they consumed, so every
--      derived number can show its working.

DROP TABLE IF EXISTS metric_inputs CASCADE;
DROP TABLE IF EXISTS metric_results CASCADE;
DROP TABLE IF EXISTS reconciliation_findings CASCADE;
DROP TABLE IF EXISTS facts CASCADE;
DROP TABLE IF EXISTS periods CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS extraction_runs CASCADE;

-- An extraction run. Keeping runs as first-class rows means an accuracy figure
-- quoted in the README is attached to a specific run over a specific corpus,
-- not to a vibe.
CREATE TABLE extraction_runs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    model           TEXT        NOT NULL,
    pages_read      INTEGER     NOT NULL,
    facts_extracted INTEGER     NOT NULL,
    precision_pct   NUMERIC(5,2),
    recall_pct      NUMERIC(5,2),
    notes           TEXT
);

CREATE TABLE documents (
    name            TEXT PRIMARY KEY,
    kind            TEXT NOT NULL CHECK (kind IN ('native', 'scanned')),
    page_count      INTEGER NOT NULL,
    published_on    DATE,
    is_audited      BOOLEAN NOT NULL DEFAULT FALSE,
    description     TEXT
);

CREATE TABLE periods (
    id              TEXT PRIMARY KEY,           -- FY2025, HY2026, H2FY2026
    period_type     TEXT NOT NULL CHECK (period_type IN ('annual', 'half_year')),
    starts_on       DATE NOT NULL,
    ends_on         DATE NOT NULL,
    months          INTEGER NOT NULL,
    is_audited      BOOLEAN NOT NULL DEFAULT FALSE,
    is_derived      BOOLEAN NOT NULL DEFAULT FALSE,  -- H2 = FY less H1
    sort_order      INTEGER NOT NULL,
    basis           TEXT
);

CREATE TABLE facts (
    id                  SERIAL PRIMARY KEY,
    period_id           TEXT NOT NULL REFERENCES periods(id),
    metric              TEXT NOT NULL,          -- canonical vocabulary
    value               NUMERIC(16,2) NOT NULL, -- sign-normalised
    value_as_printed    TEXT,                   -- exactly as the page shows it
    label_as_printed    TEXT,
    statement           TEXT NOT NULL,
    entity_scope        TEXT NOT NULL DEFAULT 'not_stated'
                        CHECK (entity_scope IN ('consolidated', 'company', 'not_stated')),
    source_document     TEXT NOT NULL REFERENCES documents(name),
    source_page         INTEGER NOT NULL,
    extraction_path     TEXT NOT NULL CHECK (extraction_path IN ('native_text', 'vision', 'derived', 'golden')),
    is_approximate      BOOLEAN NOT NULL DEFAULT FALSE,
    note                TEXT,
    run_id              INTEGER REFERENCES extraction_runs(id),
    UNIQUE (period_id, metric, entity_scope, source_document, source_page)
);

CREATE INDEX facts_period_metric ON facts (period_id, metric);

-- Reconciliation output. A finding is not necessarily an error in our pipeline -
-- D01 is an error in a published document - so severity and resolution are
-- separate from whether the check passed.
CREATE TABLE reconciliation_findings (
    id              SERIAL PRIMARY KEY,
    check_id        TEXT NOT NULL,              -- R01..R09
    period_id       TEXT REFERENCES periods(id),
    status          TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'flag', 'skip')),
    severity        TEXT CHECK (severity IN ('informational', 'low', 'medium', 'high')),
    defect_id       TEXT,                       -- D01..D03 where it is a source defect
    expected        NUMERIC(16,2),
    actual          NUMERIC(16,2),
    description     TEXT NOT NULL,
    handling        TEXT,
    run_id          INTEGER REFERENCES extraction_runs(id)
);

CREATE TABLE metric_results (
    id              SERIAL PRIMARY KEY,
    metric_id       TEXT NOT NULL,              -- gross_margin, cash_runway
    label           TEXT NOT NULL,
    period_id       TEXT NOT NULL REFERENCES periods(id),
    value           NUMERIC(20,4),
    unit            TEXT NOT NULL CHECK (unit IN ('eur', 'pct', 'months', 'ratio', 'count', 'x')),
    formula         TEXT NOT NULL,
    not_meaningful  BOOLEAN NOT NULL DEFAULT FALSE,
    is_approximate  BOOLEAN NOT NULL DEFAULT FALSE,
    flags           TEXT[],
    note            TEXT,
    run_id          INTEGER REFERENCES extraction_runs(id),
    UNIQUE (metric_id, period_id, run_id)
);

CREATE INDEX metric_results_period ON metric_results (period_id);

-- Which facts fed which metric. This is the join that powers click-through:
-- a director taps a margin and sees the two figures behind it and their pages.
CREATE TABLE metric_inputs (
    metric_result_id INTEGER NOT NULL REFERENCES metric_results(id) ON DELETE CASCADE,
    fact_id          INTEGER REFERENCES facts(id),
    input_period_id  TEXT NOT NULL,
    input_metric     TEXT NOT NULL,
    input_value      NUMERIC(16,2) NOT NULL,
    source_document  TEXT NOT NULL,
    source_page      TEXT NOT NULL,
    PRIMARY KEY (metric_result_id, input_period_id, input_metric)
);
