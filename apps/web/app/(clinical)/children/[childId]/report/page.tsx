"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api, PRODUCT } from "@/lib/api";
import { formatPercent, formatStatus } from "@/lib/utils";

export default function ReportPage() {
  const { childId } = useParams<{ childId: string }>();
  const { data } = useQuery({ queryKey: ["report", childId], queryFn: () => api<Record<string, unknown>>(`/children/${childId}/report`) });
  return (
    <article className="print-plain mx-auto max-w-3xl rounded-2xl bg-white p-8">
      <h1 className="text-2xl font-semibold">Progress summary</h1>
      <p className="text-sm text-muted">{PRODUCT.disclaimer}</p>
      <p className="mt-4 font-medium">{String(data?.pseudonymous_id ?? "")}</p>
      <pre className="mt-4 whitespace-pre-wrap text-sm">{JSON.stringify(data?.risk_history, null, 2)}</pre>
      <p className="mt-6 text-xs text-muted">Latent vector values are intentionally excluded from health-worker reports.</p>
    </article>
  );
}
