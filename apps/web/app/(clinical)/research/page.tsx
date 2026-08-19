"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ResearchDisclaimer } from "@/components/demo-banner";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";

export default function ResearchPage() {
  const profile = useQuery({ queryKey: ["dataset"], queryFn: () => api<Record<string, unknown>>("/research/dataset-profile") });
  const ablation = useQuery({ queryKey: ["ablation"], queryFn: () => api<{ message?: string; comparisons?: string[] }>("/research/ablation") });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Research analytics</h1>
      <ResearchDisclaimer />
      <Card>
        <CardHeader><CardTitle>Dataset profile</CardTitle></CardHeader>
        <CardBody className="text-sm">
          <p className="text-xs uppercase text-muted">Synthetic Demonstration Data</p>
          <pre className="mt-3 overflow-auto rounded-xl bg-canvas p-3">{JSON.stringify(profile.data, null, 2)}</pre>
        </CardBody>
      </Card>
      <Card>
        <CardHeader><CardTitle>Ablation</CardTitle></CardHeader>
        <CardBody>
          {ablation.data?.message ? <EmptyState title={ablation.data.message} /> : null}
          <ul className="list-disc pl-5 text-sm">
            {(ablation.data?.comparisons ?? []).map((c) => <li key={c}>{c}</li>)}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}
