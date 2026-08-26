import { NextResponse } from "next/server";
import { loadReport } from "@/lib/report";

/**
 * The published board report as JSON.
 *
 * Exposed so the pack can be consumed by other systems - a data room, a lender's
 * own model - without scraping the page. Read-only by design: the report is
 * built by the Python pipeline, never mutated over HTTP.
 */
export async function GET() {
  const report = await loadReport();
  return NextResponse.json(report, {
    headers: { "Cache-Control": "public, max-age=300, s-maxage=3600" },
  });
}
