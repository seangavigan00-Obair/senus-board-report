import { Pool } from "pg";

/**
 * Postgres access for provenance drill-down.
 *
 * The static board-report.json remains the source of truth for the pack
 * itself - a board report is a point-in-time document, and a director should
 * see the same numbers in January that were approved in September, not
 * whatever a live query happens to return that day. Postgres exists for the
 * layer beneath the pack: querying facts and reconciliation findings that
 * didn't make the published cut, and for the AI commentary endpoint, which
 * grounds its answers in this data rather than in the raw PDFs.
 *
 * A missing DATABASE_URL is not fatal - the report page renders from the JSON
 * regardless - so this returns null instead of throwing, and callers check.
 */
let pool: Pool | null | undefined;

export function getPool(): Pool | null {
  if (pool !== undefined) return pool;
  const url = process.env.DATABASE_URL;
  pool = url ? new Pool({ connectionString: url, max: 5 }) : null;
  return pool;
}

export interface FactRow {
  period_id: string;
  metric: string;
  value: string;
  value_as_printed: string | null;
  label_as_printed: string | null;
  statement: string;
  entity_scope: string;
  source_document: string;
  source_page: number;
  extraction_path: string;
  is_approximate: boolean;
  note: string | null;
}

export async function factsFor(period: string, metric: string): Promise<FactRow[]> {
  const db = getPool();
  if (!db) return [];
  const { rows } = await db.query<FactRow>(
    `SELECT period_id, metric, value, value_as_printed, label_as_printed,
            statement, entity_scope, source_document, source_page,
            extraction_path, is_approximate, note
     FROM facts WHERE period_id = $1 AND metric = $2
     ORDER BY source_document, source_page`,
    [period, metric],
  );
  return rows;
}

export interface ReconciliationRow {
  check_id: string;
  period_id: string | null;
  status: string;
  severity: string | null;
  defect_id: string | null;
  expected: string | null;
  actual: string | null;
  description: string;
  handling: string | null;
}

export async function reconciliationFindings(): Promise<ReconciliationRow[]> {
  const db = getPool();
  if (!db) return [];
  const { rows } = await db.query<ReconciliationRow>(
    `SELECT check_id, period_id, status, severity, defect_id, expected, actual,
            description, handling
     FROM reconciliation_findings ORDER BY period_id, check_id`,
  );
  return rows;
}

export async function isConnected(): Promise<boolean> {
  const db = getPool();
  if (!db) return false;
  try {
    await db.query("SELECT 1");
    return true;
  } catch {
    return false;
  }
}
