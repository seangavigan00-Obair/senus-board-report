"use client";

import { useMemo, useState } from "react";
import type { Audience, BoardReport, Metric } from "@/lib/types";
import { AUDIENCE_LABEL, AUDIENCE_LENS } from "@/lib/types";
import { display, formatValue, deltaLabel, trend } from "@/lib/format";
import { BarSeries, Composition, LineSeries, Waterfall, toPoints } from "./charts";
import { ComparisonTable } from "./ComparisonTable";
import { ProvenancePanel } from "./ProvenancePanel";

const AUDIENCES: Audience[] = ["management", "board", "equity", "credit"];
const PRIOR: Record<string, string> = {
  FY2025: "FY2024",
  FY2026: "FY2025",
  HY2026: "HY2025",
  H2FY2026: "H2FY2025",
};

const NAV = [
  { id: "overview", label: "Overview" },
  { id: "growth", label: "Growth & Revenue" },
  { id: "profitability", label: "Profitability" },
  { id: "liquidity", label: "Cash & Liquidity" },
  { id: "customers", label: "Customers & Channels" },
  { id: "solvency", label: "Solvency & Returns" },
  { id: "table", label: "All periods" },
  { id: "quality", label: "Data quality" },
];

export function Dashboard({ report }: { report: BoardReport }) {
  const [audience, setAudience] = useState<Audience>("board");
  const [inspecting, setInspecting] = useState<Metric | null>(null);

  const byIdPeriod = useMemo(() => {
    const out: Record<string, Record<string, Metric>> = {};
    for (const m of report.metrics) (out[m.id] ??= {})[m.period] = m;
    return out;
  }, [report.metrics]);

  const periodLabels = useMemo(
    () => Object.fromEntries(report.periods.map((p) => [p.id, p.label])),
    [report.periods],
  );
  const derivedPeriods = useMemo(
    () => new Set(report.periods.filter((p) => p.is_derived).map((p) => p.id)),
    [report.periods],
  );

  const get = (id: string, period: string) => byIdPeriod[id]?.[period];
  const latest = (id: string, order = ["FY2026", "H2FY2026", "HY2026", "FY2025"]) =>
    order.map((p) => get(id, p)).find(Boolean);

  const annual = ["FY2024", "FY2025", "FY2026"];
  const halves = ["HY2025", "H2FY2025", "HY2026", "H2FY2026"];
  const marginPeriods = ["FY2024", "FY2025", "HY2026"];
  const tablePeriods = report.periods.map((p) => p.id);

  const runway = get("cash_runway", "H2FY2026");
  const revenueFY = get("revenue", "FY2026");
  const growthFY = get("revenue_growth_yoy", "FY2026");
  const h1Growth = get("revenue_growth_yoy", "HY2026");
  const h2Growth = get("revenue_growth_yoy", "H2FY2026");
  const burn = get("monthly_burn", "H2FY2026");
  const grossMargin = latest("gross_margin");

  const bridgePeriod = "HY2026";
  const bridge = ["bridge_opening_cash", "bridge_cash_flow_from_operations",
                  "bridge_cash_flow_from_investing", "bridge_cash_flow_from_financing",
                  "bridge_closing_cash"]
    .map((id) => get(id, bridgePeriod))
    .filter(Boolean) as Metric[];

  const costPeriod = "FY2025";
  const costParts = ["cost_component_administrative_expenses",
                     "cost_component_cost_of_sales",
                     "cost_component_distribution_costs"]
    .map((id) => get(id, costPeriod))
    .filter(Boolean) as Metric[];

  const headline = latest(report.audience_headline[audience]);

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <div className="mx-auto flex max-w-[1400px]">
        {/*
          Sidebar in the brand's deep forest green, the way senus.com uses it for
          its hero sections. It stays constant in light and dark mode, so the
          product reads as Senus at a glance rather than as a generic dashboard.
        */}
        <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col bg-[var(--brand-deep)] lg:flex">
          <div className="border-b border-white/10 px-5 py-5">
            <p className="font-display text-sm font-semibold tracking-tight text-[var(--brand-deep-text)]">
              {report.entity.current_name}
            </p>
            <p className="mt-0.5 text-[11px] text-[var(--brand-deep-muted)]">
              {report.entity.ticker} · Euronext Access
            </p>
          </div>
          <nav className="flex-1 overflow-y-auto px-3 py-4">
            {NAV.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="block rounded px-2.5 py-1.5 text-xs text-[var(--brand-deep-muted)] transition
                           hover:bg-white/10 hover:text-[var(--brand-deep-text)]"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="border-t border-white/10 px-5 py-4 text-[10px] leading-relaxed text-[var(--brand-deep-muted)]">
            <p className="font-mono">build {report.build.content_hash}</p>
            <p className="mt-1">
              {report.build.metric_count} metrics · {report.build.period_count} periods
            </p>
            <p className="mt-1">
              {report.build.fact_source === "golden_set" ? "Verified facts" : "Pipeline extraction"}
            </p>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 border-b border-[var(--hairline)] bg-[var(--surface)]/95 backdrop-blur">
            <div className="px-6 py-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h1 className="font-display text-lg font-semibold tracking-tight">Board Report</h1>
                  <p className="mt-0.5 text-xs text-[var(--muted)]">
                    Year ended 30 June 2026 · unaudited · formerly {report.entity.former_name}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {AUDIENCES.map((a) => (
                    <button
                      key={a}
                      type="button"
                      onClick={() => setAudience(a)}
                      aria-pressed={audience === a}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                        audience === a
                          ? "bg-[var(--accent-strong)] text-[var(--accent-text)]"
                          : "bg-[var(--chip)] text-[var(--muted)] hover:text-[var(--text)]"
                      }`}
                    >
                      {AUDIENCE_LABEL[a]}
                    </button>
                  ))}
                </div>
              </div>
              <p className="mt-2 text-[11px] text-[var(--muted)]">{AUDIENCE_LENS[audience]}</p>
            </div>
          </header>

          <main className="px-6 py-6">
            {/* The alert comes before anything else. It is the reason for the pack. */}
            {runway && (
              <section
                id="overview"
                className="mb-6 rounded-xl border border-[var(--negative)] bg-[var(--negative-wash)] p-5"
              >
                <div className="flex flex-wrap items-start gap-6">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--negative)]">
                      Liquidity — action required
                    </p>
                    <p className="font-display mt-1 text-4xl font-semibold tabular-nums tracking-tight text-[var(--negative)]">
                      {display(runway)}
                    </p>
                    <p className="text-xs text-[var(--muted)]">
                      cash runway at 30 June 2026
                    </p>
                  </div>
                  <p className="max-w-2xl flex-1 text-sm leading-relaxed">
                    Cash fell from <strong className="tabular-nums">€735,189</strong> at
                    31 December 2025 to approximately{" "}
                    <strong className="tabular-nums">€130,000</strong> at the year end — a
                    burn of {burn ? display(burn) : "—"} a month, back to FY2024 levels
                    despite the €0.4m annualised cost reduction from the Loamin
                    integration. An €850,000 performance-linked contingent consideration
                    sits alongside it. The Board has announced its intention to raise
                    €0.5m–€1.5m.
                  </p>
                </div>
              </section>
            )}

            {/* KPI strip. Four numbers, at a glance. */}
            <section className="mb-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Kpi metric={revenueFY} prior={get("revenue", "FY2025")} caption="FY2026" onInspect={setInspecting} />
              <Kpi metric={growthFY} prior={get("revenue_growth_yoy", "FY2025")} caption="FY2026 vs FY2025" onInspect={setInspecting} />
              <Kpi metric={grossMargin} prior={get("gross_margin", "FY2025")} caption="latest reported" onInspect={setInspecting} />
              <Kpi metric={headline} caption={`Lead indicator · ${AUDIENCE_LABEL[audience]}`} onInspect={setInspecting} />
            </section>

            <Panel
              id="growth"
              title="Growth & Revenue"
              subtitle={
                h1Growth && h2Growth
                  ? `The full-year figure hides two very different halves: ${display(h1Growth)} in H1, when soil sampling was delayed by a wet winter, against ${display(h2Growth)} in H2.`
                  : undefined
              }
            >
              <div className="grid gap-8 lg:grid-cols-2">
                <Figure caption="Revenue by financial year. FY2026 is a directors' indication, not audited.">
                  <BarSeries
                    points={toPoints(annual.map((p) => get("revenue", p)), annual.map((p) => periodLabels[p] ?? p))}
                    unit="eur"
                  />
                </Figure>
                <Figure caption="Revenue by half. Second halves are derived by subtraction (FY less H1); no half-year splits are published separately.">
                  <BarSeries
                    points={toPoints(halves.map((p) => get("revenue", p)), halves.map((p) => periodLabels[p] ?? p))}
                    unit="eur"
                  />
                </Figure>
              </div>
            </Panel>

            <Panel
              id="profitability"
              title="Profitability"
              subtitle="Gross margin has widened every year while the operating loss has narrowed. The cost base is overwhelmingly administrative, not cost of delivery."
            >
              <div className="grid gap-8 lg:grid-cols-2">
                <Figure caption="Gross and operating margin. Operating margin remains deeply negative; the trend is the message.">
                  <LineSeries
                    unit="pct"
                    series={[
                      {
                        name: "Gross margin",
                        color: "var(--positive)",
                        points: toPoints(marginPeriods.map((p) => get("gross_margin", p)), marginPeriods.map((p) => periodLabels[p] ?? p)),
                      },
                      {
                        name: "Operating margin",
                        color: "var(--negative)",
                        points: toPoints(marginPeriods.map((p) => get("operating_margin", p)), marginPeriods.map((p) => periodLabels[p] ?? p)),
                      },
                    ]}
                  />
                </Figure>
                <Figure caption={`Cost base composition, ${periodLabels[costPeriod] ?? costPeriod}.`}>
                  {costParts.length > 0 ? (
                    <Composition
                      parts={costParts.map((c) => ({ label: c.label, value: c.value ?? 0 }))}
                    />
                  ) : (
                    <Empty />
                  )}
                </Figure>
              </div>
            </Panel>

            <Panel
              id="liquidity"
              title="Cash & Liquidity"
              subtitle="The December equity raise, not trading, funded the first half of FY2026."
            >
              <div className="grid gap-8 lg:grid-cols-2">
                <Figure caption={`Cash walk, ${periodLabels[bridgePeriod] ?? bridgePeriod}. Operating and investing consumed cash; financing more than replaced it.`}>
                  {bridge.length === 5 ? (
                    <Waterfall
                      steps={bridge.map((b, i) => ({
                        label: b.label,
                        value: b.value ?? 0,
                        isTotal: i === 0 || i === bridge.length - 1,
                      }))}
                    />
                  ) : (
                    <Empty />
                  )}
                </Figure>
                <Figure caption="Cash runway in months, at each period's own burn rate. The December raise bought roughly six months.">
                  <BarSeries
                    unit="months"
                    positiveColor="var(--warning)"
                    points={toPoints(
                      ["FY2024", "FY2025", "HY2026", "H2FY2026"].map((p) => get("cash_runway", p)),
                      ["FY2024", "FY2025", "HY2026", "H2FY2026"].map((p) => periodLabels[p] ?? p),
                    )}
                  />
                </Figure>
              </div>
            </Panel>

            <Panel
              id="customers"
              title="Customers & Channels"
              subtitle="Enterprise is the strategic channel, and Senus ERA carries roughly five times the contract value of soil sampling."
            >
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {["customer_accounts", "enterprise_customers", "revenue_per_account",
                  "revenue_share_enterprise_pct", "revenue_share_uk_pct",
                  "acv_enterprise_era", "acv_enterprise_terrain", "acv_enterprise_soil"]
                  .map((id) => latest(id))
                  .filter(Boolean)
                  .map((m) => (
                    <Kpi
                      key={(m as Metric).id}
                      metric={m as Metric}
                      caption={periodLabels[(m as Metric).period] ?? (m as Metric).period}
                      compact
                      onInspect={setInspecting}
                    />
                  ))}
              </div>
            </Panel>

            <Panel
              id="solvency"
              title="Solvency & Returns"
              subtitle="Both measures are shown as not meaningful, and the reason is the point: debt is serviced from cash reserves and equity, not from operations."
            >
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {["dscr", "roce", "working_capital", "ebitda"]
                  .map((id) => latest(id))
                  .filter(Boolean)
                  .map((m) => (
                    <Kpi
                      key={(m as Metric).id}
                      metric={m as Metric}
                      caption={periodLabels[(m as Metric).period] ?? (m as Metric).period}
                      onInspect={setInspecting}
                    />
                  ))}
              </div>
            </Panel>

            <Panel
              id="table"
              title="All periods"
              subtitle="Every cell is traceable — select a figure to see its formula and the pages it was read from."
            >
              <ComparisonTable
                rows={[
                  { id: "revenue", label: "Revenue" },
                  { id: "revenue_growth_yoy", label: "Revenue growth (YoY)" },
                  { id: "gross_margin", label: "Gross margin" },
                  { id: "operating_margin", label: "Operating margin" },
                  { id: "ebitda", label: "EBITDA" },
                  { id: "admin_cost_ratio", label: "Admin costs / revenue" },
                  { id: "working_capital", label: "Working capital" },
                  { id: "monthly_burn", label: "Net monthly burn" },
                  { id: "cash_runway", label: "Cash runway" },
                  { id: "dscr", label: "Debt service coverage" },
                  { id: "roce", label: "Return on capital employed" },
                ]}
                periods={tablePeriods}
                periodLabels={periodLabels}
                derivedPeriods={derivedPeriods}
                byIdPeriod={byIdPeriod}
                onInspect={setInspecting}
              />
            </Panel>

            <DataQuality report={report} />
          </main>
        </div>
      </div>

      <ProvenancePanel
        metric={inspecting}
        periodLabels={periodLabels}
        onClose={() => setInspecting(null)}
      />
    </div>
  );
}

function Panel({
  id,
  title,
  subtitle,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mb-8 scroll-mt-28 rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-5">
      <h2 className="font-display text-sm font-semibold tracking-tight">{title}</h2>
      {subtitle && (
        <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[var(--muted)]">{subtitle}</p>
      )}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Figure({ caption, children }: { caption: string; children: React.ReactNode }) {
  return (
    <figure className="min-w-0">
      {children}
      <figcaption className="mt-2 text-[11px] leading-snug text-[var(--muted)]">
        {caption}
      </figcaption>
    </figure>
  );
}

function Empty() {
  return (
    <div className="flex h-40 items-center justify-center rounded border border-dashed border-[var(--hairline)] text-xs text-[var(--muted)]">
      Not available in the published sources
    </div>
  );
}

function Kpi({
  metric,
  prior,
  caption,
  compact,
  onInspect,
}: {
  metric?: Metric;
  prior?: Metric;
  caption: string;
  compact?: boolean;
  onInspect: (m: Metric) => void;
}) {
  if (!metric) return null;
  const direction = trend(metric, prior);
  const delta = deltaLabel(metric, prior);
  const critical = metric.flags.includes("critical");

  return (
    <button
      type="button"
      onClick={() => onInspect(metric)}
      className={`group rounded-lg border p-4 text-left transition hover:border-[var(--accent)]
                  focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                    critical
                      ? "border-[var(--negative)] bg-[var(--negative-wash)]"
                      : "border-[var(--hairline)] bg-[var(--surface)]"
                  }`}
    >
      <p className="text-[11px] font-medium leading-tight text-[var(--muted)]">{metric.label}</p>
      <p
        className={`font-display mt-1.5 font-semibold tabular-nums tracking-tight ${
          compact ? "text-xl" : "text-2xl"
        } ${critical ? "text-[var(--negative)]" : ""}`}
      >
        {display(metric)}
      </p>
      <p className="mt-0.5 flex items-center gap-2 text-[10px] text-[var(--muted)]">
        <span>{caption}</span>
        {delta && (
          <span
            className={
              direction === "better"
                ? "text-[var(--positive)]"
                : direction === "worse"
                  ? "text-[var(--negative)]"
                  : ""
            }
          >
            {delta}
          </span>
        )}
        {metric.is_approximate && <span>· approximate</span>}
      </p>
    </button>
  );
}

/**
 * Data quality is part of the report, not an appendix. The pack tells the Board
 * what it does not know, and where a published source contradicts itself.
 */
function DataQuality({ report }: { report: BoardReport }) {
  return (
    <section id="quality" className="scroll-mt-28 grid gap-5 lg:grid-cols-2">
      <div className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-5">
        <h2 className="font-display text-sm font-semibold">Source document defects</h2>
        <p className="mt-1 text-[11px] text-[var(--muted)]">
          Found by automated reconciliation across the published corpus. Figures are
          reported exactly as printed and never silently corrected.
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
        <h2 className="font-display text-sm font-semibold">What this report cannot tell you</h2>
        <p className="mt-1 text-[11px] text-[var(--muted)]">
          Documented limits of the source corpus.
        </p>
        <ul className="mt-3 space-y-2">
          {report.data_gaps.map((gap, i) => (
            <li key={i} className="flex gap-2 text-xs leading-snug text-[var(--muted)]">
              <span className="text-[var(--warning)]">•</span>
              <span>{gap}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
