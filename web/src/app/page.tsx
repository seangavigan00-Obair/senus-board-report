import { Dashboard } from "@/components/Dashboard";
import { loadReport } from "@/lib/report";

export const metadata = {
  title: "Senus PLC — Board Report",
  description:
    "AI-native board report for Senus PLC, built from published financial statements with full provenance on every figure.",
};

export default async function Page() {
  const report = await loadReport();
  return <Dashboard report={report} />;
}
