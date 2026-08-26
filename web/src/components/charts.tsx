"use client";

import type { Metric, Unit } from "@/lib/types";
import { formatValue } from "@/lib/format";

/**
 * Charts for the board pack. Inline SVG, no charting dependency.
 *
 * The report has four chart shapes and a handful of series. A charting library
 * would add ~100kb and a client-render pass to draw polylines and rectangles
 * that are a few dozen lines of SVG each. Keeping them hand-written also keeps
 * the whole page server-renderable and the colour system in one place.
 *
 * Every chart shares one rule: a value that is approximate or derived renders at
 * reduced opacity, so the eye can tell a published figure from an inferred one
 * without reading a legend.
 */

const AXIS = "var(--hairline)";
const AXIS_W = 0.8;

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(Math.abs(raw) || 1)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? mag * 10;
  const start = Math.floor(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + step * 0.001; v += step) out.push(v);
  return out;
}

export interface Point {
  label: string;
  value: number | null;
  muted?: boolean;
  emphasis?: boolean;
}

/** Vertical bars across periods. The default for a revenue or absolute series. */
export function BarSeries({
  points,
  unit,
  height = 200,
  positiveColor = "var(--accent)",
  scaleMax,
}: {
  points: Point[];
  unit: Unit;
  height?: number;
  positiveColor?: string;
  /**
   * Force the top of the scale. Two charts placed side by side get compared by
   * bar height whether or not that is valid, so charts meant to be read
   * together must share a scale.
   */
  scaleMax?: number;
}) {
  const values = points.filter((p) => p.value !== null).map((p) => p.value as number);
  if (values.length === 0) return null;

  const max = Math.max(...values, 0, scaleMax ?? Number.NEGATIVE_INFINITY);
  const min = Math.min(...values, 0);
  const ticks = niceTicks(min, max);
  const top = Math.max(max, ...ticks);
  const bottom = Math.min(min, ...ticks);
  const span = top - bottom || 1;

  const padL = 58;
  const padB = 26;
  // The tallest bar carries a value label ABOVE it, so the plot area has to stop
  // short of the top of the viewBox or that label is clipped. It was.
  const padT = 22;
  const plotH = height - padB - padT;
  const y = (v: number) => padT + (1 - (v - bottom) / span) * plotH;
  const zeroY = y(0);

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 520 ${height}`}
        className="w-full min-w-[420px]"
        style={{ height }}
        role="img"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={520} y1={y(t)} y2={y(t)} stroke={AXIS} strokeWidth={AXIS_W} />
            <text
              x={padL - 8}
              y={y(t) + 3}
              textAnchor="end"
              className="fill-[var(--muted)] text-[9px] tabular-nums"
            >
              {formatValue(t, unit)}
            </text>
          </g>
        ))}

        {points.map((p, i) => {
          const slot = (520 - padL) / points.length;
          const cx = padL + slot * i + slot / 2;
          const w = Math.min(slot * 0.56, 46);
          if (p.value === null) {
            return (
              <text
                key={p.label}
                x={cx}
                y={zeroY - 6}
                textAnchor="middle"
                className="fill-[var(--muted)] text-[9px]"
              >
                —
              </text>
            );
          }
          const barTop = Math.min(y(p.value), zeroY);
          const barH = Math.max(Math.abs(y(p.value) - zeroY), 1);
          return (
            <g key={p.label}>
              <rect
                x={cx - w / 2}
                y={barTop}
                width={w}
                height={barH}
                rx={2}
                fill={p.value < 0 ? "var(--negative)" : positiveColor}
                opacity={p.muted ? 0.45 : p.emphasis ? 1 : 0.85}
              />
              <text
                x={cx}
                y={p.value < 0 ? barTop + barH + 11 : barTop - 5}
                textAnchor="middle"
                className="fill-[var(--text)] text-[9px] font-medium tabular-nums"
              >
                {formatValue(p.value, unit)}
              </text>
              <text
                x={cx}
                y={height - 8}
                textAnchor="middle"
                className="fill-[var(--muted)] text-[9px]"
              >
                {p.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** A line across periods. Used for margins, where the trend is the message. */
export function LineSeries({
  series,
  unit,
  height = 200,
}: {
  series: { name: string; color: string; points: Point[] }[];
  unit: Unit;
  height?: number;
}) {
  const all = series.flatMap((s) =>
    s.points.filter((p) => p.value !== null).map((p) => p.value as number),
  );
  if (all.length === 0) return null;

  const ticks = niceTicks(Math.min(...all, 0), Math.max(...all, 0));
  const top = Math.max(...all, ...ticks);
  const bottom = Math.min(...all, ...ticks);
  const span = top - bottom || 1;

  const padL = 58;
  const padB = 26;
  const padT = 16;
  const plotH = height - padB - padT;
  const labels = series[0]?.points.map((p) => p.label) ?? [];
  const slot = labels.length > 1 ? (520 - padL - 20) / (labels.length - 1) : 0;
  const x = (i: number) => padL + 10 + slot * i;
  const y = (v: number) => padT + (1 - (v - bottom) / span) * plotH;

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 520 ${height}`}
        className="w-full min-w-[420px]"
        style={{ height }}
        role="img"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={520} y1={y(t)} y2={y(t)} stroke={AXIS} strokeWidth={AXIS_W} />
            <text
              x={padL - 8}
              y={y(t) + 3}
              textAnchor="end"
              className="fill-[var(--muted)] text-[9px] tabular-nums"
            >
              {formatValue(t, unit)}
            </text>
          </g>
        ))}

        {series.map((s) => {
          const pts = s.points
            .map((p, i) => ({ ...p, i }))
            .filter((p) => p.value !== null);
          if (pts.length < 2) return null;
          return (
            <g key={s.name}>
              <polyline
                points={pts.map((p) => `${x(p.i)},${y(p.value as number)}`).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {pts.map((p) => (
                <circle
                  key={p.label}
                  cx={x(p.i)}
                  cy={y(p.value as number)}
                  r={3}
                  fill="var(--surface)"
                  stroke={s.color}
                  strokeWidth={2}
                  opacity={p.muted ? 0.5 : 1}
                />
              ))}
            </g>
          );
        })}

        {labels.map((label, i) => (
          <text
            key={label}
            x={x(i)}
            y={height - 8}
            textAnchor="middle"
            className="fill-[var(--muted)] text-[9px]"
          >
            {label}
          </text>
        ))}
      </svg>

      <div className="mt-1 flex flex-wrap gap-4">
        {series.map((s) => (
          <span key={s.name} className="flex items-center gap-1.5 text-[11px] text-[var(--muted)]">
            <span className="h-0.5 w-4 rounded" style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * A cash walk: opening balance, the flows that moved it, closing balance.
 *
 * Bars for the flows float at the running total, so the December equity raise is
 * visibly the thing that funded the period rather than one bar among four.
 */
export function Waterfall({
  steps,
  height = 220,
}: {
  steps: { label: string; value: number; isTotal: boolean }[];
  height?: number;
}) {
  if (steps.length < 3) return null;

  let running = 0;
  const bars = steps.map((s) => {
    if (s.isTotal) {
      running = s.value;
      return { ...s, from: 0, to: s.value };
    }
    const from = running;
    running += s.value;
    return { ...s, from, to: running };
  });

  const all = bars.flatMap((b) => [b.from, b.to, 0]);
  const ticks = niceTicks(Math.min(...all), Math.max(...all));
  const top = Math.max(...all, ...ticks);
  const bottom = Math.min(...all, ...ticks);
  const span = top - bottom || 1;

  const padL = 58;
  const padB = 26;
  const padT = 22;
  const plotH = height - padB - padT;
  const y = (v: number) => padT + (1 - (v - bottom) / span) * plotH;

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 520 ${height}`}
        className="w-full min-w-[440px]"
        style={{ height }}
        role="img"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={520} y1={y(t)} y2={y(t)} stroke={AXIS} strokeWidth={AXIS_W} />
            <text
              x={padL - 8}
              y={y(t) + 3}
              textAnchor="end"
              className="fill-[var(--muted)] text-[9px] tabular-nums"
            >
              {formatValue(t, "eur")}
            </text>
          </g>
        ))}

        {bars.map((b, i) => {
          const slot = (520 - padL) / bars.length;
          const cx = padL + slot * i + slot / 2;
          const w = Math.min(slot * 0.54, 44);
          const yTop = Math.min(y(b.from), y(b.to));
          const h = Math.max(Math.abs(y(b.to) - y(b.from)), 1.5);
          const fill = b.isTotal
            ? "var(--accent)"
            : b.value >= 0
              ? "var(--positive)"
              : "var(--negative)";
          return (
            <g key={b.label}>
              {i > 0 && (
                <line
                  x1={cx - slot / 2 - w / 2 + w / 2}
                  x2={cx - w / 2}
                  y1={y(b.isTotal ? 0 : b.from)}
                  y2={y(b.isTotal ? 0 : b.from)}
                  stroke={AXIS}
                  strokeDasharray="2 2"
                  strokeWidth={0.8}
                />
              )}
              <rect x={cx - w / 2} y={yTop} width={w} height={h} rx={2} fill={fill} />
              <text
                x={cx}
                y={yTop - 4}
                textAnchor="middle"
                className="fill-[var(--text)] text-[9px] font-medium tabular-nums"
              >
                {formatValue(b.isTotal ? b.value : b.value, "eur")}
              </text>
              <text
                x={cx}
                y={height - 8}
                textAnchor="middle"
                className="fill-[var(--muted)] text-[9px]"
              >
                {b.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** Composition of a total, as proportional bars with share labels. */
export function Composition({
  parts,
}: {
  parts: { label: string; value: number; note?: string | null }[];
}) {
  const total = parts.reduce((sum, p) => sum + Math.abs(p.value), 0) || 1;
  const colors = ["var(--accent)", "var(--warning)", "var(--muted)"];

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded">
        {parts.map((p, i) => (
          <div
            key={p.label}
            style={{
              width: `${(Math.abs(p.value) / total) * 100}%`,
              background: colors[i % colors.length],
            }}
            title={`${p.label}: ${formatValue(p.value, "eur")}`}
          />
        ))}
      </div>
      <ul className="mt-3 space-y-1.5">
        {parts.map((p, i) => (
          <li key={p.label} className="flex items-baseline justify-between gap-3 text-xs">
            <span className="flex items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-sm"
                style={{ background: colors[i % colors.length] }}
              />
              {p.label}
            </span>
            <span className="flex items-baseline gap-2 tabular-nums">
              <span className="text-[var(--muted)]">
                {((Math.abs(p.value) / total) * 100).toFixed(1)}%
              </span>
              <span className="font-medium">{formatValue(p.value, "eur")}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Turn a metric series into chart points, muting approximate and derived values. */
export function toPoints(
  metrics: (Metric | undefined)[],
  labels: string[],
): Point[] {
  return metrics.map((m, i) => ({
    label: labels[i],
    value: m && !m.not_meaningful ? m.value : null,
    muted: m?.is_approximate || m?.flags.includes("derived_from_cash_movement"),
  }));
}
