"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ResearchDisclaimer } from "@/components/demo-banner";

export default function SettingsPage() {
  const { data } = useQuery({ queryKey: ["settings"], queryFn: () => api<{ sections: string[]; clinical_policy: Record<string, unknown> }>("/admin/settings") });
  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <ResearchDisclaimer />
      <ul className="flex flex-wrap gap-2">{(data?.sections ?? []).map((s) => <li key={s} className="rounded-full border border-line bg-white px-3 py-1 text-sm">{s}</li>)}</ul>
      <div className="rounded-2xl border border-line bg-white p-5 text-sm">
        <p className="font-medium">Clinical / research policy (Research / Demo Configuration)</p>
        <pre className="mt-3 overflow-auto">{JSON.stringify(data?.clinical_policy, null, 2)}</pre>
      </div>
    </div>
  );
}
