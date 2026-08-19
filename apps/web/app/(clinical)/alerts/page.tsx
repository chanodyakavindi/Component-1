"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { formatPercent } from "@/lib/utils";
import { useState } from "react";

type Alert = {
  id: string;
  child_id: string;
  pseudonymous_id: string;
  type: string;
  severity: string;
  status: string;
  message: string;
  trigger_value?: { previous_risk?: number; current_risk?: number; risk_velocity?: number };
  created_at: string;
};

export default function AlertsPage() {
  const qc = useQueryClient();
  const [type, setType] = useState("");
  const [status, setStatus] = useState("OPEN");
  const { data, isLoading, error } = useQuery({
    queryKey: ["alerts", type, status],
    queryFn: () => api<{ items: Alert[] }>(`/alerts?type=${type}&status=${status}`),
  });
  const ack = useMutation({
    mutationFn: (id: string) => api(`/alerts/${id}/acknowledge`, { method: "PATCH", body: JSON.stringify({}) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
  if (isLoading) return <Skeleton className="h-64" />;
  if (error) return <ErrorState message="Unable to load alerts." />;
  const items = data?.items ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Alert centre</h1>
      <div className="flex flex-wrap gap-2">
        {["", "STAGNATION", "DETERIORATION", "RELAPSE", "MISSED_FOLLOW_UP"].map((t) => (
          <button key={t || "all"} onClick={() => setType(t)} className={`rounded-full border px-3 py-1 text-xs ${type === t ? "border-teal-800 bg-teal-50" : "border-line"}`}>{t || "all"}</button>
        ))}
      </div>
      {items.length === 0 ? <EmptyState title="No alerts require your attention." /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((a) => (
            <article key={a.id} className="rounded-2xl border border-line bg-white p-5 shadow-card">
              <div className="flex justify-between">
                <p className="font-semibold">{a.pseudonymous_id}</p>
                <StatusBadge value={a.severity} />
              </div>
              <p className="mt-2">{a.message}</p>
              <p className="mt-2 text-sm text-muted">
                Risk: {formatPercent(a.trigger_value?.previous_risk)} → {formatPercent(a.trigger_value?.current_risk)}
              </p>
              <div className="mt-4 flex gap-2">
                <Link href={`/children/${a.child_id}`}><Button variant="secondary">Open child</Button></Link>
                {a.status === "OPEN" ? <Button onClick={() => ack.mutate(a.id)}>Acknowledge</Button> : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
