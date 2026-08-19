"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { DemoBanner } from "@/components/demo-banner";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { formatPercent } from "@/lib/utils";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";

type Dashboard = {
  synthetic: boolean;
  kpis: { children_under_monitoring: number; high_risk: number; stagnation_alerts: number; deteriorating: number; missed_follow_ups: number };
  attention: { child_id: string; pseudonymous_id: string; status?: string; current_risk?: number; trend?: string; alert?: string; next_action?: string }[];
  risk_trend: { improving: number; stable: number; stagnating: number; deteriorating: number };
  upcoming_follow_ups: { child: string; date: string; clinic: string; status: string }[];
  recent_activity: { action: string; resource_type: string; timestamp: string }[];
};

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard") });
  const [filter, setFilter] = useState("all");
  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
    );
  }
  if (error || !data) return <ErrorState message="Dashboard is temporarily unavailable." />;
  const kpis = [
    ["Children Under Monitoring", data.kpis.children_under_monitoring],
    ["High-Risk Children", data.kpis.high_risk],
    ["Stagnation Alerts", data.kpis.stagnation_alerts],
    ["Deteriorating", data.kpis.deteriorating],
    ["Missed Follow-Ups", data.kpis.missed_follow_ups],
  ] as const;
  const filtered = data.attention.filter((row) => {
    if (filter === "all") return true;
    if (filter === "critical") return (row.current_risk ?? 0) >= 0.7 || row.alert === "DETERIORATION";
    if (filter === "deterioration") return row.alert === "DETERIORATION";
    if (filter === "stagnation") return row.alert === "STAGNATION";
    if (filter === "missed") return row.alert === "MISSED_FOLLOW_UP";
    return true;
  });
  const chart = [
    { name: "Improving", n: data.risk_trend.improving },
    { name: "Stable", n: data.risk_trend.stable },
    { name: "Stagnating", n: data.risk_trend.stagnating },
    { name: "Deteriorating", n: data.risk_trend.deteriorating },
  ];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Priority actions</h1>
          <p className="text-sm text-muted">AI-assisted decision support. Clinical review required.</p>
        </div>
        <DemoBanner compact />
      </div>
      {data.synthetic ? <p className="text-xs uppercase tracking-wide text-muted">Synthetic Demonstration Data</p> : null}
      <section className="grid gap-4 md:grid-cols-5">
        {kpis.map(([label, value]) => (
          <Card key={label}>
            <CardBody className="pt-5">
              <p className="text-sm text-muted">{label}</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums">{value}</p>
            </CardBody>
          </Card>
        ))}
      </section>
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>Children Requiring Attention</CardTitle>
          <div className="flex flex-wrap gap-2">
            {["all", "critical", "deterioration", "stagnation", "missed"].map((key) => (
              <button key={key} onClick={() => setFilter(key)} className={`rounded-full border px-3 py-1 text-xs capitalize ${filter === key ? "border-teal-800 bg-teal-50" : "border-line"}`}>
                {key}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardBody>
          {filtered.length === 0 ? (
            <EmptyState title="No alerts require your attention." body="When stagnation, deterioration or missed follow-ups occur, they will appear here." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-muted">
                  <tr>
                    <th className="py-2">Child ID</th>
                    <th>Status</th>
                    <th>Current risk</th>
                    <th>Trend</th>
                    <th>Alert</th>
                    <th>Next action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.alert + row.child_id} className="border-t border-line">
                      <td className="py-3 font-medium">
                        <Link className="text-teal-800 underline-offset-2 hover:underline" href={`/children/${row.child_id}`}>{row.pseudonymous_id}</Link>
                      </td>
                      <td><StatusBadge value={row.status} /></td>
                      <td>{formatPercent(row.current_risk)}</td>
                      <td><StatusBadge value={row.trend} /></td>
                      <td><StatusBadge value={row.alert} /></td>
                      <td>{row.next_action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Risk trend</CardTitle></CardHeader>
          <CardBody className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart}>
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="n" fill="#0F766E" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
        <Card>
          <CardHeader><CardTitle>Upcoming follow-ups</CardTitle></CardHeader>
          <CardBody>
            {data.upcoming_follow_ups.length === 0 ? <EmptyState title="No follow-ups are scheduled." /> : (
              <ul className="space-y-3 text-sm">
                {data.upcoming_follow_ups.map((f) => (
                  <li key={f.child + f.date} className="flex justify-between gap-3 border-b border-line pb-2">
                    <span className="font-medium">{f.child}</span>
                    <span className="text-muted">{f.date} · {f.clinic}</span>
                    <StatusBadge value={f.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Recent activity</CardTitle></CardHeader>
        <CardBody>
          <ul className="space-y-2 text-sm">
            {data.recent_activity.map((a, i) => (
              <li key={i} className="flex justify-between gap-4 border-b border-line py-2">
                <span>{a.action.replaceAll("_", " ")} · {a.resource_type}</span>
                <span className="text-muted">{new Date(a.timestamp).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}
