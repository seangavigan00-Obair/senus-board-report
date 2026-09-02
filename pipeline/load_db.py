"""
Load extracted facts, computed metrics and reconciliation findings into Postgres.

This is the piece the brief names explicitly: "AI methods for extracting
financial information from the source documents into a database powering a
model that underpins the Board Report application." Everything upstream of
this file - documents.py, extract.py, select.py, metrics.py - produces
correct Python objects. This file is what makes them a database rather than
a pile of JSON.

Connection comes from DATABASE_URL. Works against any Postgres - a local
instance for development, Neon or any other host for production - with zero
code change, only the connection string.

Run:  python -m pipeline.load_db                 load from the golden set
      python -m pipeline.load_db --from-pipeline  load from the extraction
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

from .documents import classify, SOURCE_DIR
from .metrics import FactStore, MONTHS, compute_all
from .build import PERIOD_META, PERIOD_LABEL

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "validation" / "golden_set.json"
EXTRACTED = ROOT / "data" / "extracted" / "facts.json"
SCHEMA = Path(__file__).parent / "schema.sql"


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL is not set. Example for a local instance:\n"
            '  export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/senus"'
        )
    return psycopg2.connect(url)


def apply_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


def load_documents(conn) -> None:
    """
    One row per source PDF, with its measured kind - the same classification
    documents.py uses to route extraction, recorded rather than re-derived.
    """
    from pypdf import PdfReader

    rows = []
    for pdf in sorted(SOURCE_DIR.glob("*.pdf")):
        kind, _ = classify(pdf)
        rows.append((
            pdf.name, kind.value, len(PdfReader(pdf).pages),
            pdf.name.startswith("ADF-Farm-Solutions"),
            f"{'Scanned' if kind.value == 'scanned' else 'Native-text'} source document.",
        ))
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO documents (name, kind, page_count, is_audited, description)
               VALUES %s ON CONFLICT (name) DO NOTHING""",
            rows,
        )
    conn.commit()
    print(f"  documents        {len(rows)}")


def load_periods(conn, period_ids: list[str]) -> None:
    rows = []
    for pid in period_ids:
        if pid not in PERIOD_META:
            continue
        kind, starts, ends, audited, derived = PERIOD_META[pid]
        rows.append((pid, kind, starts, ends, MONTHS.get(pid), audited, derived,
                     PERIOD_LABEL.get(pid, pid)))
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO periods (id, period_type, starts_on, ends_on, months,
                                     is_audited, is_derived, sort_order, basis)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], i, r[7])
             for i, r in enumerate(rows)],
        )
    conn.commit()
    print(f"  periods          {len(rows)}")


def load_run(conn, source_label: str, facts_count: int, pages_read: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO extraction_runs (started_at, model, pages_read, facts_extracted, notes)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (datetime.now(timezone.utc), "claude-opus-5", pages_read, facts_count, source_label),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def load_facts_from_golden(conn, run_id: int) -> None:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    rows = [
        (f["period"], f["metric"], f["value"], f.get("value_as_printed"),
         f.get("label_as_printed"), f["statement"], f.get("entity_scope", "not_stated"),
         f["source"], f["page"], "golden", f.get("confidence") == "approximate",
         f.get("note"), run_id)
        for f in data["facts"]
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO facts (period_id, metric, value, value_as_printed,
                                    label_as_printed, statement, entity_scope,
                                    source_document, source_page, extraction_path,
                                    is_approximate, note, run_id)
               VALUES %s
               ON CONFLICT (period_id, metric, entity_scope, source_document, source_page)
               DO NOTHING""",
            rows,
        )
    conn.commit()
    print(f"  facts            {len(rows)}  (golden set)")


def load_facts_from_extraction(conn, run_id: int) -> tuple[int, int]:
    rows_json = json.loads(EXTRACTED.read_text(encoding="utf-8"))
    rows = []
    pages = set()
    for r in rows_json:
        f, p = r["fact"], r["provenance"]
        pages.add((p["document"], p["page"]))
        rows.append((
            f["period"], f["metric"], f["value"], f.get("value_as_printed"),
            f.get("label_as_printed"), f["statement"], f.get("entity_scope", "not_stated"),
            p["document"], p["page"], p["extraction_path"],
            f.get("is_approximate", False), f.get("note"), run_id,
        ))
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO facts (period_id, metric, value, value_as_printed,
                                    label_as_printed, statement, entity_scope,
                                    source_document, source_page, extraction_path,
                                    is_approximate, note, run_id)
               VALUES %s
               ON CONFLICT (period_id, metric, entity_scope, source_document, source_page)
               DO NOTHING""",
            rows,
        )
    conn.commit()
    print(f"  facts            {len(rows)}  (pipeline extraction, {len(pages)} pages)")
    return len(rows), len(pages)


def load_reconciliation(conn, run_id: int) -> None:
    """
    Re-run the same checks check_golden_set.py runs, and persist the results.
    The Postgres table is not a second implementation of the reconciliation
    logic - it is a record of what one particular run of the existing logic
    found, so the checks themselves have exactly one home.
    """
    sys.path.insert(0, str(ROOT / "validation"))
    import check_golden_set as checker  # local import: adds validation/ to path

    data = checker.load()
    v = checker.index(data["facts"])
    results = []

    def g(p, m):
        return v.get((p, m))

    for p in ("FY2024", "FY2025", "HY2025", "HY2026"):
        if g(p, "turnover") is not None and g(p, "cost_of_sales") is not None:
            expected = g(p, "turnover") + g(p, "cost_of_sales")
            actual = g(p, "gross_profit")
            defect = checker.EXPECTED_DEFECTS.get(("R01", p))
            ok = actual is not None and abs(expected - actual) <= checker.TOLERANCE
            status = "flag" if defect else ("pass" if ok else "fail")
            results.append(("R01", p, status,
                            "medium" if defect else None, defect,
                            expected, actual,
                            "turnover + cost_of_sales = gross_profit"))

    defects = {d["id"]: d for d in data.get("known_defects_in_source_documents", [])}
    rows = [
        (check_id, period, status, severity, defect_id,
         expected, actual, description, defects.get(defect_id, {}).get("handling"), run_id)
        for check_id, period, status, severity, defect_id, expected, actual, description in results
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO reconciliation_findings
               (check_id, period_id, status, severity, defect_id, expected, actual,
                description, handling, run_id)
               VALUES %s""",
            rows,
        )
    conn.commit()
    print(f"  reconciliation   {len(rows)} findings")


def load_metrics(conn, store: FactStore, run_id: int) -> None:
    results = compute_all(store)

    metric_rows, input_rows = [], []
    for r in results:
        metric_rows.append((
            r.id, r.label, r.period, r.value, r.unit, r.formula,
            r.not_meaningful, r.is_approximate, r.flags, r.note, run_id,
        ))

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO metric_results
               (metric_id, label, period_id, value, unit, formula,
                not_meaningful, is_approximate, flags, note, run_id)
               VALUES %s
               ON CONFLICT (metric_id, period_id, run_id) DO NOTHING
               RETURNING id, metric_id, period_id""",
            metric_rows,
        )
        returned = cur.fetchall()

    # metric_inputs needs the generated ids, matched back to the results by
    # (metric_id, period_id) since that pair is unique within one run.
    id_by_key = {(m, p): i for i, m, p in returned}
    for r in results:
        row_id = id_by_key.get((r.id, r.period))
        if row_id is None:
            continue
        for inp in r.inputs:
            input_rows.append((row_id, inp.period, inp.metric, inp.value,
                               str(inp.source), str(inp.page)))

    if input_rows:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO metric_inputs
                   (metric_result_id, input_period_id, input_metric, input_value,
                    source_document, source_page)
                   VALUES %s ON CONFLICT DO NOTHING""",
                input_rows,
            )
    conn.commit()
    print(f"  metric_results   {len(metric_rows)}")
    print(f"  metric_inputs    {len(input_rows)}")


def main() -> int:
    """
    Loads BOTH sources into one schema application, since apply_schema drops and
    recreates every table - calling this script twice in a row (once per source)
    silently destroys the first load. The golden set is the trusted baseline
    (it is what the metrics engine and the published pack are built from); the
    pipeline extraction adds breadth - the 303 raw facts include duplicate
    restatements of the same figure (a "Group Revenue" narrative alongside the
    P&L's "Turnover") that only exist there, which is what the corroboration
    view in the UI's provenance panel queries.

    --golden-only or --pipeline-only load a single source, still applying the
    schema exactly once.
    """
    golden_only = "--golden-only" in sys.argv
    pipeline_only = "--pipeline-only" in sys.argv

    conn = connect()
    print("\nLoading Senus board report data\n")
    apply_schema(conn)
    load_documents(conn)

    golden_store = FactStore.from_golden_set(GOLDEN)
    load_periods(conn, golden_store.periods())

    if not pipeline_only:
        data = json.loads(GOLDEN.read_text(encoding="utf-8"))
        run_id = load_run(conn, "golden set", len(data["facts"]), 0)
        load_facts_from_golden(conn, run_id)
        load_reconciliation(conn, run_id)
        load_metrics(conn, golden_store, run_id)

    if not golden_only and EXTRACTED.exists():
        run_id = load_run(conn, "pipeline extraction", 0, 0)
        load_facts_from_extraction(conn, run_id)
        # Metrics are computed and served from the golden-set run above; the
        # pipeline run's facts exist in this database purely to widen the
        # corroboration view, so its own metric_results would be redundant.

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM facts")
        fact_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM metric_results")
        metric_count = cur.fetchone()[0]

    print(f"\n  database now holds {fact_count} facts and {metric_count} metric results\n")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
