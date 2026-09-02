import { NextResponse } from "next/server";
import { isConnected } from "@/lib/db";

/** Whether the database is reachable. The report itself never depends on this. */
export async function GET() {
  const database = await isConnected();
  return NextResponse.json({ status: "ok", database });
}
