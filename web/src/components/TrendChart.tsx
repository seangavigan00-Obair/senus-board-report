"use client";

import type { Metric } from "@/lib/types";
import { formatValue } from "@/lib/format";

/**
 * A small inline SVG series. No charting library.
 *
 * Deliberate: the whole report has five metric shapes and a handful of series,
 * and a 100kb dependency to draw a polyline is weight a board pack does not need
 * to carry. It also keeps the page fully self-contained and server-renderable.
 *
 * Bars rather than a line where the series contains a sign change - a line
 * crossing zero reads as a trend, when the crossing IS the story.
 */
export function TrendChart({
  series,
  periodLabels,
  height = 76,
}: {
  series: { period: string; metric: Metric | undefined }[];
  periodLabels: Record<string, string>;
  height?: number;
}) {
  const points = series
    .map((s) => ({
      period: s.period,
      value: s.metric && !s.metric.not_meaningful ? s.metric.value : null,
      unit: s.metric?.unit ?? "eur",
      derived: s.metric?.flags.includes("derived_from_cash_movement") ?? false,
      approximate: s.metric?.is_approximate ?? false,
    }))
    .filter((p) => p.value !== null) as {
    period: string;
    value: number;
    unit: Metric["unit"];
    derived: boolean;
    approximate: boolean;
  }[];

  if (points.length < 2) return null;

  const values = points.map((p) => p.value);
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;

  const W = 100;
  const padY = 8;
  const usableH = height - padY * 2;
  const step = points.length > 1 ? W / (points.length - 1) : W;
  const y = (v: number) => padY + (1 - (v - min) / span) * usableH;
  const zeroY = y(0);
  const crossesZero = min < 0 && max > 0;

  return (
    <div className="mt-3">
      <svg
        viewBox={`0 0 ${W} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`Trend across ${points.length} periods`}
      >
        {crossesZero && (
          <line
            x1={0}
            x2={W}
            y1={zeroY}
            y2={zeroY}
            stroke="var(--hairline)"
            strokeWidth={0.5}
            vectorEffect="non-scaling-stroke"
          />
        )}

        {crossesZero ? (
          points.map((p, i) => {
            const barX = i * step;
            const top = Math.min(y(p.value), zeroY);
            const h = Math.abs(y(p.value) - zeroY);
            return (
              <rect
                key={p.period}
                x={barX - step * 0.22}
                width={step * 0.44}
                y={top}
                height={Math.max(h, 0.6)}
                fill={p.value < 0 ? "var(--negative)" : "var(--positive)"}
                opacity={p.approximate ? 0.55 : 1}
              />
            );
          })
        ) : (
          <>
            <polyline
              points={points.map((p, i) => `${i * step},${y(p.value)}`).join(" ")}
              fill="none"
              stroke="var(--accent)"
              strokeWidth={1.6}
              strokeLinejoin="round"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
            {points.map((p, i) => (
              <circle
                key={p.period}
                cx={i * step}
                cy={y(p.value)}
                r={1.8}
                fill="var(--accent)"
                opacity={p.approximate || p.derived ? 0.5 : 1}
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </>
        )}
      </svg>

      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted)]">
        <span>
          {periodLabels[points[0].period] ?? points[0].period}{" "}
          {formatValue(points[0].value, points[0].unit)}
        </span>
        <span className="text-right">
          {periodLabels[points[points.length - 1].period] ??
            points[points.length - 1].period}{" "}
          {formatValue(
            points[points.length - 1].value,
            points[points.length - 1].unit,
          )}
        </span>
      </div>
    </div>
  );
}
