/**
 * Types mirroring the payload emitted by pipeline/build.py.
 *
 * Kept hand-written rather than generated: the payload is a stable published
 * contract between the Python side and the UI, and a change to it should be a
 * deliberate edit in two places rather than something a codegen step absorbs
 * silently.
 */

export type Unit = "eur" | "pct" | "months" | "ratio" | "count" | "x";

export type Audience = "management" | "board" | "equity" | "credit";

export interface MetricInput {
  period: string;
  metric: string;
  value: number;
  source: string;
  page: number | string;
  is_approximate: boolean;
}

export interface Metric {
  id: string;
  label: string;
  period: string;
  value: number | null;
  unit: Unit;
  formula: string;
  flags: string[];
  note: string | null;
  not_meaningful: boolean;
  is_approximate: boolean;
  inputs: MetricInput[];
}

export interface Period {
  id: string;
  label: string;
  type: "annual" | "half_year";
  starts_on: string;
  ends_on: string;
  months: number | null;
  is_audited: boolean;
  is_derived: boolean;
  basis: string | null;
}

export interface Section {
  id: string;
  title: string;
  metrics: string[];
  audiences: Audience[];
}

export interface SourceDefect {
  id: string;
  severity: "informational" | "low" | "medium" | "high";
  source: string;
  page: number | string;
  period?: string;
  description: string;
  corroboration?: string;
  conclusion?: string;
  handling: string;
  why_this_matters?: string;
}

export interface Strategy {
  name: string;
  revenue_cagr_target_pct: number;
  baseline_period: string;
  baseline_revenue: number;
  target_period: string;
  ebitda_positive_target: string;
  enterprise_customers_target: number;
  acv_target: number;
  ireland_revenue_share_target_pct: number;
  source: string;
}

export interface BoardReport {
  build: {
    generated_at: string;
    fact_source: "golden_set" | "pipeline_extraction";
    fact_source_file: string;
    metric_count: number;
    period_count: number;
    content_hash: string;
  };
  entity: {
    current_name: string;
    former_name: string;
    ticker: string;
    venue: string;
    isin: string;
    admission_date: string;
    issued_share_capital: number;
    financial_year_end: string;
  };
  currency: string;
  periods: Period[];
  sections: Section[];
  audience_headline: Record<Audience, string>;
  metrics: Metric[];
  source_defects: SourceDefect[];
  data_gaps: string[];
  strategy: Strategy;
}

export const AUDIENCE_LABEL: Record<Audience, string> = {
  management: "Management",
  board: "Board",
  equity: "Equity investors",
  credit: "Credit providers",
};

/** What each audience is actually reading the pack for. Shown under the toggle. */
export const AUDIENCE_LENS: Record<Audience, string> = {
  management:
    "Operational control: where cash is going and whether cost discipline is holding.",
  board:
    "Fiduciary view: solvency, runway and whether the Senus 2030 plan remains credible.",
  equity:
    "Growth and the path to profitability, measured against the 50% CAGR target.",
  credit:
    "Ability to service and repay debt: liquidity, coverage and headroom.",
};
