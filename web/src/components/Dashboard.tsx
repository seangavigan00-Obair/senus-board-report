"use client";

import { useMemo, useState } from "react";
import type { Audience, BoardReport, Metric } from "@/lib/types";
import { AUDIENCE_LABEL, AUDIENCE_LENS } from "@/lib/types";
import { display, formatValue } from "@/lib/format";
import { MetricCard } from "./MetricCard";
import { ProvenancePanel } from "./ProvenancePanel";

const AUDIENCES: Audience[] = ["management", "board", "equity", "credit"];
const PRIOR: Record<string, string> = {
  FY2025: "FY2024",
  FY2026: "FY2025",
  HY2026: "HY2025",
  H2FY2026: "H2FY2025",
};

export function Dashboard({ report }: { report: BoardReport }) {
  const [audience, setAudience] = useState<Audience>("board");
  const [inspecting, setInspecting] = useState<Metric | null>(null);
  const [showDerived, setShowDerived] = useState(false);

  const byIdPeriod = useMemo(() => {
    const out: Record<string, Record<string, Metric>> = {};
    for (const m of report.metrics) (out[m.id] ??= {})[m.period] = m;
    return out;
  }, [report.metrics]);

  const periodLabels = useMemo(
    () => Object.fromEntries(report.periods.map((p) => [p.id, p.label])),
    [report.periods],
  );

  // The reporting period is the latest one with real published substance.
  const focusPeriod = "FY2026";
  const seriesPeriods = useMemo(
    () =>
      report.periods
        .filter((p) => showDerived || !p.is_derived)
        .map((p) => p.id),
    [report.periods, showDerived],
  );

  const sections = report.sections.filter((s) => s.audiences.includes(audience));
  const headlineId = report.audience_headline[audience];
  const headline = byIdPeriod[headlineId]?.[focusPeriod]
    ?? byIdPeriod[headlineId]?.["H2FY2026"];

  const runway = byIdPeriod["cash_runway"]?.["H2FY2026"];
  const revenue = byIdPeriod["revenue"]?.[focusPeriod];
  const h1Growth = byIdPeriod["revenue_growth_yoy"]?.["HY2026"];
  const h2Growth = byIdPeriod["revenue_growth_yoy"]?.["H2FY2026"];

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--hairline)] bg-[var(--surface)]">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                {report.entity.current_name} — Board Report
              </h1>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Year ended 30 June 2026 · {report.entity.ticker} on{" "}
                {report.entity.venue} · formerly {report.entity.former_name}
              </p>
            </div>
            <div className="text-right text-[11px] text-[var(--muted)]">
              <p>
                Built {new Date(report.build.generated_at).toLocaleDateString("en-IE")}
              </p>
              <p className="font-mono">build {report.build.content_hash}</p>
              <p>
                {report.build.metric_count} metrics ·{" "}
                {report.build.fact_source === "golden_set"
                  ? "verified facts"
                  : "pipeline extraction"}
              </p>
            </div>
          </div>

          <nav className="mt-5 flex flex-wrap items-center gap-2" aria-label="Audience">
            {AUDIENCES.map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAudience(a)}
                aria-pressed={audience === a}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  audience === a
                    ? "bg-[var(--accent)] text-[var(--accent-text)]"
                    : "bg-[var(--chip)] text-[var(--muted)] hover:text-[var(--text)]"
                }`}
              >
                {AUDIENCE_LABEL[a]}
              </button>
            ))}
            <span className="ml-1 text-[11px] text-[var(--muted)]">
              {AUDIENCE_LENS[audience]}
            </span>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Executive summary. The one thing this audience must not miss. */}
        <section className="mb-10 rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
            Executive summary
          </h2>

          <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-3 text-sm leading-relaxed">
              <p>
                Revenue closed FY2026 at{" "}
                <strong className="tabular-nums">
                  {revenue ? display(revenue) : "—"}
                </strong>
                , up{" "}
                <strong className="tabular-nums">
                  {byIdPeriod["revenue_growth_yoy"]?.[focusPeriod]
                    ? display(byIdPeriod["revenue_growth_yoy"][focusPeriod])
                    : "—"}
                </strong>{" "}
                on FY2025. That full-year figure conceals two very different
                halves: growth of{" "}
                <strong className="tabular-nums">
                  {h1Growth ? display(h1Growth) : "—"}
                </strong>{" "}
                in H1, when soil sampling was delayed by a wet winter, against{" "}
                <strong className="tabular-nums">
                  {h2Growth ? display(h2Growth) : "—"}
                </strong>{" "}
                in H2.
              </p>
              <p>
                Gross margin has widened every year — 62.8% in FY2024 to 81.7% at
                the half year — and the operating loss narrowed 46% in FY2025.
                The operating trend is genuinely improving.
              </p>
              <p className="rounded-lg border border-[var(--negative)] bg-[var(--negative-wash)] px-4 py-3">
                <strong>Liquidity is the binding constraint.</strong> Cash fell
                from €735,189 at 31 December 2025 to approximately €130,000 at
                the year end — a burn of about €100,865 a month, back to FY2024
                levels despite the €0.4m annualised cost reduction from the
                Loamin integration. That leaves{" "}
                <strong className="tabular-nums">
                  {runway ? display(runway) : "—"}
                </strong>{" "}
                of runway at the year-end burn rate, alongside an €850,000
                performance-linked contingent consideration. The Board has
                announced its intention to raise €0.5m–€1.5m.
              </p>
            </div>

            <div className="space-y-3">
              {headline && (
                <div className="rounded-lg border border-[var(--hairline)] p-4">
                  <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
                    Lead indicator · {AUDIENCE_LABEL[audience]}
                  </p>
                  <p className="mt-1 text-3xl font-semibold tabular-nums tracking-tight">
                    {display(headline)}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--muted)]">
                    {headline.label} ·{" "}
                    {periodLabels[headline.period] ?? headline.period}
                  </p>
                </div>
              )}

              <div className="rounded-lg border border-[var(--hairline)] p-4">
                <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
                  {report.strategy.name} target
                </p>
                <p className="mt-1 text-sm">
                  {report.strategy.revenue_cagr_target_pct}% revenue CAGR to{" "}
                  {report.strategy.target_period}, from a{" "}
                  {formatValue(report.strategy.baseline_revenue, "eur")}{" "}
                  {report.strategy.baseline_period} base.
                </p>
                <p className="mt-2 text-xs text-[var(--muted)]">
                  FY2026 delivered{" "}
                  {byIdPeriod["revenue_growth_yoy"]?.[focusPeriod]
                    ? display(byIdPeriod["revenue_growth_yoy"][focusPeriod])
                    : "—"}
                  . EBITDA positive targeted in{" "}
                  {report.strategy.ebitda_positive_target}.
                </p>
              </div>
            </div>
          </div>
        </section>

        <div className="mb-4 flex items-center justify-between">
          <p className="text-[11px] text-[var(--muted)]">
            Every figure is traceable — select any card to see its formula and
            source pages.
          </p>
          <label className="flex cursor-pointer items-center gap-2 text-[11px] text-[var(--muted)]">
            <input
              type="checkbox"
              checked={showDerived}
              onChange={(e) => setShowDerived(e.target.checked)}
              className="accent-[var(--accent)]"
            />
            Show derived half-year periods
          </label>
        </div>

        {sections.map((section) => {
          const cards = section.metrics
            .map((id) => {
              const forPeriod =
                byIdPeriod[id]?.[focusPeriod] ??
                byIdPeriod[id]?.["H2FY2026"] ??
                byIdPeriod[id]?.["HY2026"] ??
                byIdPeriod[id]?.["FY2025"];
              return forPeriod ? { id, metric: forPeriod } : null;
            })
            .filter(Boolean) as { id: string; metric: Metric }[];

          if (cards.length === 0) return null;

          return (
            <section key={section.id} className="mb-9">
              <h2 className="mb-3 text-sm font-semibold tracking-tight">
                {section.title}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {cards.map(({ id, metric }) => (
                  <MetricCard
                    key={id}
                    metric={metric}
                    prior={byIdPeriod[id]?.[PRIOR[metric.period] ?? ""]}
                    series={seriesPeriods.map((p) => ({
                      period: p,
                      metric: byIdPeriod[id]?.[p],
                    }))}
                    periodLabels={periodLabels}
                    onInspect={setInspecting}
                  />
                ))}
              </div>
            </section>
          );
        })}

        <DataQuality report={report} />
      </main>

      <ProvenancePanel
        metric={inspecting}
        periodLabels={periodLabels}
        onClose={() => setInspecting(null)}
      />
    </div>
  );
}

/**
 * Data quality is part of the report, not an appendix.
 *
 * The pack tells the Board what it does not know, and where a published source
 * contradicts itself. Burying that would be the opposite of the point.
 */
function DataQuality({ report }: { report: BoardReport }) {
  return (
    <section className="mt-12 grid gap-5 lg:grid-cols-2">
      <div className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-5">
        <h2 className="text-sm font-semibold">Source document defects</h2>
        <p className="mt-1 text-[11px] text-[var(--muted)]">
          Found by automated reconciliation across the published corpus. Figures
          are reported exactly as printed and never silently corrected.
        </p>
        <ul className="mt-3 space-y-3">
          {report.source_defects.map((d) => (
            <li key={d.id} className="rounded border border-[var(--hairline)] p-3">
              <div className="flex items-center gap-2">
                <span className="rounded bg-[var(--chip)] px-1.5 py-0.5 font-mono text-[10px]">
                  {d.id}
                </span>
                <span className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
                  {d.severity}
                </span>
              </div>
              <p className="mt-1.5 text-xs leading-snug">{d.description}</p>
              <p className="mt-1.5 text-[11px] leading-snug text-[var(--muted)]">
                <strong>Handling:</strong> {d.handling}
              </p>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-5">
        <h2 className="text-sm font-semibold">What this report cannot tell you</h2>
        <p className="mt-1 text-[11px] text-[var(--muted)]">
          Documented limits of the source corpus.
        </p>
        <ul className="mt-3 space-y-2">
          {report.data_gaps.map((gap, i) => (
            <li
              key={i}
              className="flex gap-2 text-xs leading-snug text-[var(--muted)]"
            >
              <span className="text-[var(--warning)]">•</span>
              <span>{gap}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
