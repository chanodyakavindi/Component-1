"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatPercent, ageLabel } from "@/lib/utils";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Suspense, useState } from "react";

type Item = {
  id: string;
  pseudonymous_id: string;
  age_months: number;
  sex: string;
  last_visit?: string;
  current_status?: string;
  current_risk?: number;
  progress?: string;
  next_follow_up?: string;
};

function ChildrenTable() {
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState("");
  const query = useQuery({
    queryKey: ["children", q, status, progress],
    queryFn: () => api<{ items: Item[]; total: number }>(`/children?q=${encodeURIComponent(q)}&nutritional_status=${status}&progress=${progress}`),
  });
  if (query.isLoading) return <Skeleton className="h-64" />;
  if (query.isError) return <ErrorState message="Unable to load the child registry." />;
  const items = query.data?.items ?? [];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Child registry</h1>
          <p className="text-sm text-muted">Pseudonymous identifiers only. Synthetic demonstration data.</p>
        </div>
        <Link href="/children/new"><Button>Register child</Button></Link>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <Input placeholder="Search child ID" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="normal">Normal</option>
          <option value="wasting">Wasting</option>
          <option value="stunting">Stunting</option>
          <option value="underweight">Underweight</option>
        </Select>
        <Select value={progress} onChange={(e) => setProgress(e.target.value)}>
          <option value="">All progress</option>
          <option value="improving">Improving</option>
          <option value="stagnating">Stagnating</option>
          <option value="deteriorating">Deteriorating</option>
        </Select>
      </div>
      {items.length === 0 ? <EmptyState title="No children match the current filters." /> : (
        <div className="overflow-x-auto rounded-2xl border border-line bg-white shadow-card">
          <table className="w-full text-left text-sm">
            <thead className="bg-canvas text-muted">
              <tr>
                <th className="px-4 py-3">Child ID</th>
                <th>Age</th>
                <th>Sex</th>
                <th>Last visit</th>
                <th>Status</th>
                <th>Risk</th>
                <th>Progress</th>
                <th>Next follow-up</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t border-line">
                  <td className="px-4 py-3 font-medium">
                    <Link className="text-teal-800 hover:underline" href={`/children/${row.id}`}>{row.pseudonymous_id}</Link>
                  </td>
                  <td>{ageLabel(row.age_months)}</td>
                  <td className="capitalize">{row.sex}</td>
                  <td>{row.last_visit ? new Date(row.last_visit).toLocaleDateString() : "—"}</td>
                  <td><StatusBadge value={row.current_status} /></td>
                  <td>{formatPercent(row.current_risk)}</td>
                  <td><StatusBadge value={row.progress} /></td>
                  <td>{row.next_follow_up ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function ChildrenPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64" />}>
      <ChildrenTable />
    </Suspense>
  );
}
