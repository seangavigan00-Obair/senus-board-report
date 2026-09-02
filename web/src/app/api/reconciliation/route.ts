import { NextResponse } from "next/server";
import { reconciliationFindings } from "@/lib/db";

/** All reconciliation findings from Postgres, including checks that passed. */
export async function GET() {
  const findings = await reconciliationFindings();
  return NextResponse.json({ findings });
}
