import type { Metric, Unit } from "./types";

/**
 * Formatting rules for a board pack.
 *
 * Two conventions here are finance conventions rather than display preferences:
 *
 *   Losses and outflows are shown in brackets, the way every statement in the
 *   source corpus shows them. A director reading "(633,694)" knows instantly it
 *   is a loss; "-633694" makes them stop and parse.
 *
 *   A metric that is not meaningful renders as "n/m", never as a number. See
 *   pipeline/metrics.py for why ROCE and DSCR are suppressed while the company
 *   is loss-making.
 */

const eur0 = new Intl.NumberFormat("en-IE", { maximumFractionDigits: 0 });
const eur1 = new Intl.NumberFormat("en-IE", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function formatValue(value: number | null, unit: Unit): string {
  if (value === null || Number.isNaN(value)) return "—";

  switch (unit) {
    case "eur": {
      const magnitude = Math.abs(value);
      const body =
        magnitude >= 1_000_000
          ? `€${eur1.format(magnitude / 1_000_000)}m`
          : magnitude >= 10_000
            ? `€${eur0.format(magnitude / 1_000)}k`
            : `€${eur0.format(magnitude)}`;
      return value < 0 ? `(${body})` : body;
    }
    case "pct": {
      const body = `${eur1.format(Math.abs(value))}%`;
      return value < 0 ? `(${body})` : body;
    }
    case "months":
      return `${eur1.format(value)} mo`;
    case "x":
      return `${eur1.format(value)}×`;
    case "count":
      return eur0.format(value);
    default:
      return eur1.format(value);
  }
}

/** Full precision, for the provenance panel where the exact figure matters. */
export function formatExact(value: number, currency = "EUR"): string {
  const body = new Intl.NumberFormat("en-IE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Math.abs(value));
  const symbol = currency === "EUR" ? "€" : "";
  return value < 0 ? `(${symbol}${body})` : `${symbol}${body}`;
}

export function display(metric: Metric): string {
  return metric.not_meaningful ? "n/m" : formatValue(metric.value, metric.unit);
}

/**
 * Direction of travel, given what "good" means for this metric.
 * Burn falling is good even though the number is getting smaller in magnitude;
 * a loss narrowing is good even though it stays negative.
 */
const HIGHER_IS_BETTER: Record<string, boolean> = {
  revenue: true,
  revenue_growth_yoy: true,
  gross_margin: true,
  operating_margin: true,
  ebitda: true,
  ebitda_margin: true,
  working_capital: true,
  cash_runway: true,
  monthly_burn: true, // less negative is better
  dscr: true,
  roce: true,
  admin_cost_ratio: false,
};

export type Trend = "better" | "worse" | "flat" | "none";

export function trend(current: Metric, prior?: Metric): Trend {
  if (!prior || current.value === null || prior.value === null) return "none";
  if (current.not_meaningful || prior.not_meaningful) return "none";

  const delta = current.value - prior.value;
  const scale = Math.max(Math.abs(prior.value), 1);
  if (Math.abs(delta) / scale < 0.01) return "flat";

  const higherIsBetter = HIGHER_IS_BETTER[current.id] ?? true;
  const improving = higherIsBetter ? delta > 0 : delta < 0;
  return improving ? "better" : "worse";
}

export function deltaLabel(current: Metric, prior?: Metric): string | null {
  if (!prior || current.value === null || prior.value === null) return null;
  if (current.not_meaningful || prior.not_meaningful) return null;

  if (current.unit === "pct") {
    const pts = current.value - prior.value;
    return `${pts >= 0 ? "+" : ""}${eur1.format(pts)} pts`;
  }
  if (prior.value === 0) return null;
  const pct = ((current.value - prior.value) / Math.abs(prior.value)) * 100;
  if (!Number.isFinite(pct)) return null;
  return `${pct >= 0 ? "+" : ""}${eur1.format(pct)}%`;
}

/** Severity styling for a runway or coverage warning. */
export function severityOf(metric: Metric): "critical" | "warning" | null {
  if (metric.flags.includes("critical")) return "critical";
  if (metric.flags.includes("warning")) return "warning";
  return null;
}
