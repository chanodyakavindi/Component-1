"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyState } from "@/components/ui/states";

export default function VisitsPage() {
  const { data } = useQuery({ queryKey: ["follow-ups"], queryFn: () => api<{ items: { id: string; child: string; expected_date: string; status: string }[] }>("/follow-ups") });
  const items = data?.items ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Visit & follow-up schedule</h1>
      {items.length === 0 ? <EmptyState title="No follow-ups are scheduled." /> : (
        <table className="w-full rounded-2xl border border-line bg-white text-left text-sm">
          <thead className="text-muted"><tr><th className="p-3">Child</th><th>Date</th><th>Status</th></tr></thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} className="border-t border-line">
                <td className="p-3 font-medium">{r.child}</td>
                <td>{r.expected_date}</td>
                <td><StatusBadge value={r.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
