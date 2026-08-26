import { promises as fs } from "node:fs";
import path from "node:path";
import type { BoardReport, Metric } from "./types";

/**
 * Server-side access to the published board report.
 *
 * The payload is read from disk rather than fetched, so the page renders on the
 * server with no client round-trip and no loading state. In deployment the
 * database remains the system of record for drill-down; this file is the
 * published pack, fixed at a content hash so a director sees the same numbers
 * in January that were approved in September.
 */

let cached: BoardReport | null = null;

export async function loadReport(): Promise<BoardReport> {
  if (cached) return cached;
  const file = path.join(process.cwd(), "public", "board-report.json");
  cached = JSON.parse(await fs.readFile(file, "utf-8")) as BoardReport;
  return cached;
}

/** Index metrics by id then period for O(1) lookup in the render path. */
export function indexMetrics(
  metrics: Metric[],
): Record<string, Record<string, Metric>> {
  const out: Record<string, Record<string, Metric>> = {};
  for (const m of metrics) {
    (out[m.id] ??= {})[m.period] = m;
  }
  return out;
}

/**
 * The periods a board pack actually leads with.
 *
 * Derived second halves are analytically the most revealing series in this
 * dataset - they are what separates the weather-hit H1 FY2026 from the 30%
 * growth in H2 - but a pack that opens with eight columns is unreadable. The
 * primary series is the published full years plus the latest half.
 */
export function primaryPeriods(report: BoardReport): string[] {
  return report.periods
    .filter((p) => p.type === "annual" || p.id === "HY2026")
    .map((p) => p.id);
}

export function allPeriods(report: BoardReport): string[] {
  return report.periods.map((p) => p.id);
}

/** Prior comparable period, matching the metrics engine's own rule. */
export const PRIOR_PERIOD: Record<string, string> = {
  FY2025: "FY2024",
  FY2026: "FY2025",
  HY2026: "HY2025",
  H2FY2026: "H2FY2025",
};
