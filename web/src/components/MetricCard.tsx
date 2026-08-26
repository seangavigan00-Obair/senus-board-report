"use client";

import type { Metric, Period } from "@/lib/types";
import { display, deltaLabel, severityOf, trend } from "@/lib/format";
import { TrendChart } from "./TrendChart";

/**
 * One metric, at one period, with its trend and a way into its provenance.
 *
 * The whole card is a button. Every figure in this report is traceable, and
 * making the affordance the card rather than a small "info" icon is what makes
 * a director actually check a number instead of taking it on trust.
 */
export function MetricCard({
  metric,
  prior,
  series,
  periodLabels,
  onInspect,
}: {
  metric: Metric;
  prior?: Metric;
  series: { period: string; metric: Metric | undefined }[];
  periodLabels: Record<string, string>;
  onInspect: (metric: Metric) => void;
}) {
  const severity = severityOf(metric);
  const direction = trend(metric, prior);
  const delta = deltaLabel(metric, prior);

  const tone =
    severity === "critical"
      ? "border-[var(--negative)] bg-[var(--negative-wash)]"
      : severity === "warning"
        ? "border-[var(--warning)] bg-[var(--warning-wash)]"
        : "border-[var(--hairline)] bg-[var(--surface)]";

  const deltaTone =
    direction === "better"
      ? "text-[var(--positive)]"
      : direction === "worse"
        ? "text-[var(--negative)]"
        : "text-[var(--muted)]";

  return (
    <button
      type="button"
      onClick={() => onInspect(metric)}
      className={`group flex w-full flex-col rounded-lg border p-4 text-left transition
                  hover:border-[var(--accent)] focus:outline-none focus-visible:ring-2
                  focus-visible:ring-[var(--accent)] ${tone}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium leading-tight text-[var(--muted)]">
          {metric.label}
        </span>
        <span
          className="shrink-0 text-[10px] text-[var(--muted)] opacity-0 transition
                     group-hover:opacity-100 group-focus-visible:opacity-100"
        >
          source ↗
        </span>
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span
          className={`text-2xl font-semibold tabular-nums tracking-tight ${
            severity === "critical" ? "text-[var(--negative)]" : ""
          }`}
        >
          {display(metric)}
        </span>
        {delta && (
          <span className={`text-xs font-medium tabular-nums ${deltaTone}`}>
            {delta}
          </span>
        )}
      </div>

      <div className="mt-1 flex flex-wrap gap-1">
        {metric.is_approximate && <Chip>approximate</Chip>}
        {metric.not_meaningful && <Chip>not meaningful</Chip>}
        {metric.flags.includes("derived_non_gaap") && <Chip>non-GAAP</Chip>}
        {metric.flags.includes("source_inconsistent") && (
          <Chip tone="warn">source does not foot</Chip>
        )}
        {metric.flags.includes("derived_from_cash_movement") && (
          <Chip>derived from cash movement</Chip>
        )}
      </div>

      <TrendChart series={series} periodLabels={periodLabels} />

      {metric.note && (
        <p className="mt-2 line-clamp-3 text-[11px] leading-snug text-[var(--muted)]">
          {metric.note}
        </p>
      )}
    </button>
  );
}

function Chip({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "warn";
}) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
        tone === "warn"
          ? "bg-[var(--warning-wash)] text-[var(--warning-text)]"
          : "bg-[var(--chip)] text-[var(--muted)]"
      }`}
    >
      {children}
    </span>
  );
}

export function PeriodBadge({ period }: { period: Period }) {
  const label = period.is_audited
    ? "audited"
    : period.is_derived
      ? "derived"
      : "unaudited";
  return (
    <span className="rounded bg-[var(--chip)] px-1.5 py-0.5 text-[10px] text-[var(--muted)]">
      {label}
    </span>
  );
}
