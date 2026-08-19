"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { ResearchDisclaimer } from "@/components/demo-banner";
import { EmptyState } from "@/components/ui/states";

export default function ModelsPage() {
  const comparison = useQuery({ queryKey: ["model-comparison"], queryFn: () => api<{ message?: string; models?: Record<string, { f1_macro?: number; recall_macro?: number; balanced_accuracy?: number; latency_ms?: number; brier?: number }>; context?: string }>("/research/model-comparison") });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<{ model_key: string; version: string; architecture: string; status: string; is_demo: boolean }[]>("/models") });
  const data = comparison.data;
  const rows = data?.models ? Object.entries(data.models) : [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Research evaluation</h1>
      <p className="text-sm text-muted">{data?.context ?? "Research Evaluation — not a clinical patient workflow"}</p>
      <ResearchDisclaimer />
      <Card>
        <CardHeader><CardTitle>Registered models</CardTitle></CardHeader>
        <CardBody>
          <table className="w-full text-left text-sm">
            <thead><tr><th>Model</th><th>Architecture</th><th>Status</th></tr></thead>
            <tbody>
              {(models.data ?? []).map((m) => (
                <tr key={m.model_key + m.version} className="border-t border-line">
                  <td className="py-2">{m.model_key}-{m.version}{m.is_demo ? " (demo)" : ""}</td>
                  <td>{m.architecture}</td>
                  <td>{m.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
      <Card>
        <CardHeader><CardTitle>Baseline comparison</CardTitle></CardHeader>
        <CardBody>
          {rows.length === 0 ? <EmptyState title="No experimental result available" body="Run python -m ml.training.train_baselines to generate metrics. Numbers are never fabricated." /> : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th>Model</th><th className="text-right">Macro F1</th><th className="text-right">Recall</th>
                  <th className="text-right">Balanced accuracy</th><th className="text-right">Latency</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([name, m]) => (
                  <tr key={name} className="border-t border-line">
                    <td className="py-2">{name}</td>
                    <td className="text-right">{m.f1_macro?.toFixed(3) ?? "—"}</td>
                    <td className="text-right">{m.recall_macro?.toFixed(3) ?? "—"}</td>
                    <td className="text-right">{m.balanced_accuracy?.toFixed(3) ?? "—"}</td>
                    <td className="text-right">{m.latency_ms ? `${m.latency_ms.toFixed(1)} ms` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
