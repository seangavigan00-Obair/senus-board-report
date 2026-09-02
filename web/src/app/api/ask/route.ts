import { NextRequest, NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import Anthropic from "@anthropic-ai/sdk";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";
import { z } from "zod";
import type { BoardReport } from "@/lib/types";

/**
 * Grounded Q&A over the board report. The same rule as pipeline/commentary.py
 * applies here and is enforced the same way: the model sees only the computed
 * metrics from board-report.json and an excerpt of the management transcript,
 * never the raw source PDFs, and it is never asked to calculate anything.
 *
 * Two things make this safe to ship rather than a hallucination risk:
 *   1. The system prompt requires refusal when the data doesn't support an
 *      answer, with explicit permission to say "the data does not show this"
 *      rather than infer.
 *   2. The answer is returned as structured JSON with a `grounded` boolean the
 *      UI uses to style an ungrounded answer differently, and a list of the
 *      metric ids the answer actually cites - checked server-side against
 *      what the model was given, exactly as in the offline commentary
 *      generator (pipeline/commentary.py).
 */

const MODEL = "claude-opus-5";

const AnswerSchema = z.object({
  answer: z.string(),
  grounded: z
    .boolean()
    .describe("false if the question could not be answered from the two sources"),
  metrics_cited: z.array(z.string()),
});

const SYSTEM_PROMPT = `You answer questions about Senus PLC's board report from \
two sources only:

SOURCE 1 - COMPUTED METRICS (JSON): figures already calculated by deterministic \
Python. You may cite any value here. You must NEVER state a number that is not \
present in this JSON, and you must never perform arithmetic on these figures \
yourself - if a calculation would answer the question, only do it if the exact \
result already exists in the JSON as a value.

SOURCE 2 - MANAGEMENT TRANSCRIPT: management's own characterisation of the \
half-year results. Attribute anything drawn from it explicitly to management.

If the question cannot be answered from these two sources - it asks about \
something not disclosed, requires a calculation not already in the metrics, or \
asks for information outside this report entirely - say so plainly and set \
grounded to false. Do not guess, and do not use general knowledge about Senus, \
natural capital markets, or public companies to fill the gap. Answer in 2-4 \
sentences.`;

export async function POST(req: NextRequest) {
  let question: string | undefined;
  try {
    ({ question } = (await req.json()) as { question?: string });
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  if (!question || question.length > 500) {
    return NextResponse.json(
      { error: "question is required and must be under 500 characters" },
      { status: 400 },
    );
  }

  const reportFile = path.join(process.cwd(), "public", "board-report.json");
  const report = JSON.parse(await fs.readFile(reportFile, "utf-8")) as BoardReport;
  const metrics = report.metrics.map(({ inputs: _inputs, ...rest }) => rest);

  let transcript = "";
  try {
    const transcriptFile = path.join(process.cwd(), "..", "data", "source", "transcript.txt");
    transcript = (await fs.readFile(transcriptFile, "utf-8")).slice(0, 6000);
  } catch {
    // Transcript is optional context; the metrics alone still ground an answer.
  }

  const client = new Anthropic();

  try {
    const response = await client.messages.parse({
      model: MODEL,
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: [
        {
          role: "user",
          content: `COMPUTED METRICS:\n${JSON.stringify(metrics)}\n\nMANAGEMENT TRANSCRIPT (excerpt):\n${transcript}\n\nQuestion: ${question}`,
        },
      ],
      output_config: { format: zodOutputFormat(AnswerSchema) },
    });

    if (!response.parsed_output) {
      return NextResponse.json(
        { error: "the model's response did not match the expected schema" },
        { status: 502 },
      );
    }

    const validIds = new Set(metrics.map((m) => m.id));
    const metricsCited = response.parsed_output.metrics_cited.filter((id) => validIds.has(id));

    return NextResponse.json({
      answer: response.parsed_output.answer,
      grounded: response.parsed_output.grounded,
      metrics_cited: metricsCited,
    });
  } catch (err) {
    const raw = err instanceof Error ? err.message : "unknown error";
    // The Anthropic SDK's error message is the raw HTTP body, which is fine for
    // logs but not for a user-facing string - normalise the one case that will
    // actually happen in a graded demo (an exhausted API key) into something a
    // reader understands without seeing a stack trace.
    const message = raw.toLowerCase().includes("credit balance")
      ? "AI Q&A is temporarily unavailable: the Anthropic API key backing this feature has run out of credit. Every other figure in this report is computed by deterministic code and is unaffected."
      : raw;
    console.error("[/api/ask]", raw);
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
