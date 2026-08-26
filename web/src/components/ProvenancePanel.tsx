"use client";

import { useEffect } from "react";
import type { Metric } from "@/lib/types";
import { display, formatExact } from "@/lib/format";

/**
 * The audit trail for one number.
 *
 * This panel is the point of the whole project. It shows the formula that
 * produced a figure, every fact that fed it, and the document and page each
 * fact was read from - so a director can check a number rather than trust it.
 * A board report where the figures cannot be traced is a slide deck.
 */
export function ProvenancePanel({
  metric,
  periodLabels,
  onClose,
}: {
  metric: Metric | null;
  periodLabels: Record<string, string>;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!metric) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [metric, onClose]);

  if (!metric) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
      />

      <aside
        className="relative flex h-full w-full max-w-lg flex-col overflow-y-auto
                   border-l border-[var(--hairline)] bg-[var(--surface)] shadow-2xl"
      >
        <header className="sticky top-0 border-b border-[var(--hairline)] bg-[var(--surface)] px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
                {periodLabels[metric.period] ?? metric.period}
              </p>
              <h2 className="mt-0.5 text-lg font-semibold">{metric.label}</h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded px-2 py-1 text-sm text-[var(--muted)] hover:bg-[var(--chip)]"
            >
              Close
            </button>
          </div>
          <p className="mt-3 text-3xl font-semibold tabular-nums tracking-tight">
            {display(metric)}
          </p>
        </header>

        <div className="space-y-6 px-6 py-5">
          <Block title="How this was calculated">
            <code className="block rounded bg-[var(--chip)] px-3 py-2 font-mono text-xs leading-relaxed">
              {metric.formula}
            </code>
            <p className="mt-2 text-xs text-[var(--muted)]">
              Computed in Python by the metrics engine. No language model is
              involved in any calculation in this report.
            </p>
          </Block>

          <Block title={`Source figures (${metric.inputs.length})`}>
            <ul className="space-y-2">
              {metric.inputs.map((input) => (
                <li
                  key={`${input.period}-${input.metric}`}
                  className="rounded border border-[var(--hairline)] px-3 py-2"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-xs font-medium">
                      {input.metric.replace(/_/g, " ")}
                      <span className="ml-1.5 text-[var(--muted)]">
                        {periodLabels[input.period] ?? input.period}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-xs tabular-nums">
                      {formatExact(input.value)}
                    </span>
                  </div>
                  <p className="mt-1 break-words text-[11px] leading-snug text-[var(--muted)]">
                    {input.source}
                    {typeof input.page === "number" ? ` · page ${input.page}` : ` · ${input.page}`}
                    {input.is_approximate && " · stated as approximate"}
                  </p>
                </li>
              ))}
            </ul>
          </Block>

          {metric.note && (
            <Block title="Analyst note">
              <p className="text-xs leading-relaxed text-[var(--text)]">{metric.note}</p>
            </Block>
          )}

          {metric.flags.length > 0 && (
            <Block title="Flags">
              <div className="flex flex-wrap gap-1.5">
                {metric.flags.map((flag) => (
                  <span
                    key={flag}
                    className="rounded bg-[var(--chip)] px-2 py-1 font-mono text-[10px] text-[var(--muted)]"
                  >
                    {flag}
                  </span>
                ))}
              </div>
            </Block>
          )}
        </div>
      </aside>
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
        {title}
      </h3>
      {children}
    </section>
  );
}
