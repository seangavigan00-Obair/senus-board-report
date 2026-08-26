"use client";

import type { Metric } from "@/lib/types";
import { display, trend } from "@/lib/format";

/**
 * The period comparison table.
 *
 * The most familiar artefact in any board pack, and the one view where a
 * director can scan the whole business at once. Rows are metrics, columns are
 * periods, and every cell is clickable through to its provenance.
 *
 * Derived second halves are included but visually recessed: they are the most
 * analytically revealing columns in this dataset and the least official.
 */
export function ComparisonTable({
  rows,
  periods,
  periodLabels,
  derivedPeriods,
  byIdPeriod,
  onInspect,
}: {
  rows: { id: string; label: string }[];
  periods: string[];
  periodLabels: Record<string, string>;
  derivedPeriods: Set<string>;
  byIdPeriod: Record<string, Record<string, Metric>>;
  onInspect: (m: Metric) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--hairline)] bg-[var(--surface)]">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--hairline)]">
            <th className="sticky left-0 z-10 bg-[var(--surface)] px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
              Metric
            </th>
            {periods.map((p) => (
              <th
                key={p}
                className={`px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide ${
                  derivedPeriods.has(p) ? "text-[var(--muted)]/70" : "text-[var(--muted)]"
                }`}
              >
                {periodLabels[p] ?? p}
                {derivedPeriods.has(p) && (
                  <span className="block text-[9px] font-normal normal-case">derived</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const cells = byIdPeriod[row.id] ?? {};
            if (periods.every((p) => !cells[p])) return null;
            return (
              <tr
                key={row.id}
                className="border-b border-[var(--hairline)] last:border-0 hover:bg-[var(--chip)]/50"
              >
                <td className="sticky left-0 z-10 bg-inherit px-4 py-2.5 text-xs font-medium">
                  {row.label}
                </td>
                {periods.map((p) => {
                  const metric = cells[p];
                  if (!metric) {
                    return (
                      <td key={p} className="px-4 py-2.5 text-right text-xs text-[var(--muted)]">
                        —
                      </td>
                    );
                  }
                  const priorId = PRIOR[p];
                  const direction = trend(metric, priorId ? cells[priorId] : undefined);
                  return (
                    <td key={p} className="px-4 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={() => onInspect(metric)}
                        className={`rounded px-1.5 py-0.5 text-xs tabular-nums transition
                                    hover:bg-[var(--chip)] focus:outline-none
                                    focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                                      metric.not_meaningful
                                        ? "text-[var(--muted)]"
                                        : direction === "better"
                                          ? "text-[var(--positive)]"
                                          : direction === "worse"
                                            ? "text-[var(--negative)]"
                                            : ""
                                    } ${metric.is_approximate ? "opacity-70" : ""}`}
                        title={metric.formula}
                      >
                        {display(metric)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const PRIOR: Record<string, string> = {
  FY2025: "FY2024",
  FY2026: "FY2025",
  HY2026: "HY2025",
  H2FY2026: "H2FY2025",
};
