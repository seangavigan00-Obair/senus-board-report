import { NextRequest, NextResponse } from "next/server";
import { factsFor } from "@/lib/db";

/**
 * Fact-level provenance from Postgres: every source row behind one
 * (period, metric) pair, each with its document, page and printed value.
 *
 * This is the layer beneath the published pack. The board-report.json payload
 * carries the ONE fact each metric used, chosen by source precedence
 * (pipeline/select.py); this endpoint can show all of them, including ones a
 * KPI disclosure or a narrative restatement that lost to a primary statement -
 * useful for an analyst who wants to see the corroborating figures, not just
 * the winner.
 */
export async function GET(req: NextRequest) {
  const period = req.nextUrl.searchParams.get("period");
  const metric = req.nextUrl.searchParams.get("metric");
  if (!period || !metric) {
    return NextResponse.json(
      { error: "period and metric query params are required" },
      { status: 400 },
    );
  }
  const facts = await factsFor(period, metric);
  return NextResponse.json({ period, metric, facts });
}
