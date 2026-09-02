"use client";

import { useState } from "react";

interface Answer {
  answer: string;
  grounded: boolean;
  metrics_cited: string[];
}

const SUGGESTIONS = [
  "How many months of cash runway does Senus have?",
  "Why did revenue growth look weak at the half year?",
  "Is Senus profitable?",
];

/**
 * Live grounded Q&A - POSTs to /api/ask, which answers only from the computed
 * metrics and the management transcript (see that route's docstring for the
 * grounding rule). This is the interactive counterpart to the offline
 * per-audience commentary: same sources, same refusal rule, asked on demand
 * rather than pre-written.
 */
export function AskCard({ onInspectMetric }: { onInspectMetric: (id: string) => void }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "request failed");
      setAnswer(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--hairline)] bg-[var(--surface)] p-5 shadow-[0_1px_2px_rgba(16,33,29,0.05)]">
      <h2 className="font-display text-base font-semibold tracking-tight text-[var(--brand-deep)]">
        Ask about this report
      </h2>
      <p className="mt-1 text-[13px] leading-relaxed text-[var(--muted)]">
        Answered only from the computed metrics on this page and management&apos;s
        own results presentation - never the raw filings. If the data doesn&apos;t
        support an answer, it will say so.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="mt-3 flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What is driving the operating loss?"
          maxLength={500}
          className="flex-1 rounded-lg border border-[var(--hairline)] bg-[var(--bg)] px-3 py-2
                     text-sm outline-none focus:border-[var(--accent-strong)]"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded-lg bg-[var(--accent-strong)] px-4 py-2 text-sm font-medium
                     text-white transition disabled:opacity-40"
        >
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setQuestion(s);
              ask(s);
            }}
            className="rounded-full bg-[var(--chip)] px-2.5 py-1 text-[11px] text-[var(--muted)]
                       transition hover:text-[var(--text)]"
          >
            {s}
          </button>
        ))}
      </div>

      {error && <p className="mt-3 text-sm text-[var(--negative)]">{error}</p>}

      {answer && (
        <div className="mt-4 rounded-lg bg-[var(--chip)] p-3.5">
          {!answer.grounded && (
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--warning-text)]">
              Not answerable from this report
            </p>
          )}
          <p className="text-sm leading-relaxed">{answer.answer}</p>
          {answer.metrics_cited.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {answer.metrics_cited.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => onInspectMetric(id)}
                  className="rounded-full bg-[var(--surface)] px-2.5 py-1 text-[11px] font-medium
                             text-[var(--muted)] transition hover:bg-[var(--accent)] hover:text-white"
                >
                  {id.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
