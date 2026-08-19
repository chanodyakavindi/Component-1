"use client";

import { ResearchDisclaimer } from "@/components/demo-banner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useState } from "react";

export default function ReportsPage() {
  const [msg, setMsg] = useState<string | null>(null);
  async function exportData() {
    const ok = window.confirm("Export de-identified research rows? Direct identity fields will be excluded and the action will be audited.");
    if (!ok) return;
    const data = await api<{ confirmation: string; rows: unknown[] }>("/research/export", { method: "POST" });
    setMsg(`${data.confirmation} (${data.rows.length} rows)`);
  }
  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold">Reports</h1>
      <ResearchDisclaimer />
      <p className="text-sm text-muted">Health-worker progress summaries are available from each child profile. Research export is permissioned and audited.</p>
      <Button onClick={exportData}>Export de-identified dataset</Button>
      {msg ? <p className="text-sm">{msg}</p> : null}
    </div>
  );
}
