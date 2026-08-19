"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { DemoBanner } from "@/components/demo-banner";

export default function SystemPage() {
  const { data } = useQuery({ queryKey: ["system"], queryFn: () => api<Record<string, unknown>>("/admin/system") });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">System health</h1>
      <DemoBanner compact />
      <div className="grid gap-4 md:grid-cols-3">
        {["api", "database", "redis"].map((k) => (
          <Card key={k}>
            <CardHeader><CardTitle className="capitalize">{k}</CardTitle></CardHeader>
            <CardBody>{String(data?.[k] ?? "…")}</CardBody>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle>Inference</CardTitle></CardHeader>
        <CardBody>
          <pre className="overflow-auto text-sm">{JSON.stringify(data?.inference, null, 2)}</pre>
          <p className="mt-2 text-sm">Active model: {JSON.stringify(data?.active_model)}</p>
        </CardBody>
      </Card>
    </div>
  );
}
