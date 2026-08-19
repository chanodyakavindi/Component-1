"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, PRODUCT } from "@/lib/api";
import { DemoBanner } from "@/components/demo-banner";
import { RiskRing } from "@/components/risk-ring";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { ageLabel, formatPercent, formatStatus } from "@/lib/utils";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";
import { AlertTriangle, ArrowRight, Cpu } from "lucide-react";

type Profile = {
  id: string;
  pseudonymous_id: string;
  age_months: number;
  sex: string;
  facility?: { name: string; code: string };
  synthetic: boolean;
  current?: {
    visit_date: string;
    prediction?: { status: string; severity: string; risk: number; confidence: string; mode: string; model: string };
    progress?: string;
    risk_velocity?: number;
    baseline_recovery_rate?: number;
    warning?: string;
  };
  risk_change_pp?: number;
  next_follow_up?: string;
  model_warning?: string;
  visits: {
    id: string;
    visit_number: number;
    visit_date: string;
    prediction?: { status: string; severity: string; risk: number; mode: string; model: string };
    progress?: string;
    risk_velocity?: number;
    projection?: { x: number; y: number };
    embedding_space_id?: string;
    warning?: string;
  }[];
  alerts: { id: string; type: string; severity: string; status: string; message: string; trigger_value?: { previous_risk?: number; current_risk?: number; risk_velocity?: number } }[];
  notes: { id: string; body: string; created_at: string }[];
};

const TABS = ["Overview", "Visit History", "Progress & Trajectory", "Risk Factors", "Alerts", "Clinical Notes", "Model Information"];

export default function ChildProfilePage() {
  const params = useParams<{ childId: string }>();
  const qc = useQueryClient();
  const [tab, setTab] = useState("Overview");
  const [note, setNote] = useState("");
  const profile = useQuery({ queryKey: ["child", params.childId], queryFn: () => api<Profile>(`/children/${params.childId}`) });
  const acknowledge = useMutation({
    mutationFn: (id: string) => api(`/alerts/${id}/acknowledge`, { method: "PATCH", body: JSON.stringify({}) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["child", params.childId] }),
  });
  const addNote = useMutation({
    mutationFn: () => api(`/children/${params.childId}/notes`, { method: "POST", body: JSON.stringify({ body: note }) }),
    onSuccess: () => {
      setNote("");
      qc.invalidateQueries({ queryKey: ["child", params.childId] });
    },
  });
  const reassess = useMutation({
    mutationFn: () => {
      const data = profile.data!;
      const last = data.visits.at(-1);
      return api("/integrations/counterfactual/request", {
        method: "POST",
        body: JSON.stringify({
          child_id: data.pseudonymous_id,
          visit_id: last?.id,
          trigger: "STAGNATION",
          current_prediction: last?.prediction ?? {},
          current_risk: last?.prediction?.risk ?? 0,
          trajectory_summary: { progress: data.current?.progress },
          model_version: last?.prediction?.model ?? "MCA-2026-001",
        }),
      });
    },
  });

  if (profile.isLoading) return <Skeleton className="h-96" />;
  if (profile.isError || !profile.data) return <ErrorState message="This child record is unavailable or you are not authorized to view it." />;
  const d = profile.data;
  const pred = d.current?.prediction;
  const chart = d.visits.filter((v) => v.prediction).map((v) => ({
    date: new Date(v.visit_date).toLocaleDateString(undefined, { month: "short" }),
    risk: Math.round((v.prediction!.risk) * 100),
  }));
  const openAlert = d.alerts.find((a) => a.status === "OPEN");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-white px-4 py-2 text-sm">
        <span className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-clinical-ok" aria-hidden />
          DEMO ENGINE · NOT CLINICALLY VALIDATED
        </span>
        <span className="text-muted">Model {pred?.model ?? "MCA-2026-001"} · Last evaluated {d.current ? new Date(d.current.visit_date).toLocaleString() : "—"}</span>
      </div>
      <DemoBanner />

      <section className="overflow-hidden rounded-2xl border border-line bg-white shadow-card">
        <div className="grid gap-6 p-6 lg:grid-cols-[1fr_auto]">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-semibold">{d.pseudonymous_id}</h1>
              <StatusBadge value="FOLLOWING" />
            </div>
            <p className="mt-1 text-muted">
              {ageLabel(d.age_months)} · {formatStatus(d.sex)} · {d.facility?.name}
            </p>
            <p className="mt-6 text-xs uppercase tracking-wide text-muted">Current nutritional status</p>
            <p className="text-2xl font-semibold">{pred ? `${formatStatus(pred.severity)} ${formatStatus(pred.status)}` : "No prediction yet"}</p>
            <div className="mt-6 flex flex-wrap gap-10">
              <div>
                <p className="text-3xl font-semibold tabular-nums">{formatPercent(pred?.risk)}</p>
                <p className="text-xs uppercase tracking-wide text-muted">Current risk</p>
              </div>
              <div>
                <p className="text-3xl font-semibold tabular-nums">
                  {d.current?.risk_velocity != null ? `${d.current.risk_velocity > 0 ? "+" : ""}${Math.round(d.current.risk_velocity * 100)}% / month` : "—"}
                </p>
                <p className="text-xs uppercase tracking-wide text-muted">Recovery velocity</p>
              </div>
              <div>
                <p className="text-3xl font-semibold tabular-nums">{d.risk_change_pp != null ? `${d.risk_change_pp > 0 ? "+" : ""}${d.risk_change_pp} pp` : "—"}</p>
                <p className="text-xs uppercase tracking-wide text-muted">Risk change</p>
              </div>
            </div>
            <div className="mt-5">
              <p className="text-xs uppercase tracking-wide text-muted">Progress status</p>
              <div className="mt-1"><StatusBadge value={d.current?.progress} /></div>
            </div>
            <p className="mt-4 text-sm text-muted">Next follow-up {d.next_follow_up ?? "not scheduled"}</p>
          </div>
          <RiskRing value={pred?.risk} />
        </div>
        <div className="border-t border-line px-6 py-4">
          <p className="text-xs uppercase tracking-wide text-muted">Risk history</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            {d.visits.map((v, i) => (
              <span key={v.id} className="flex items-center gap-2">
                <span className="font-semibold tabular-nums">{formatPercent(v.prediction?.risk)}</span>
                <span className="text-muted">{new Date(v.visit_date).toLocaleDateString(undefined, { month: "short" })}</span>
                {i < d.visits.length - 1 ? <span className="text-line">──────</span> : null}
              </span>
            ))}
          </div>
          {d.current?.progress === "stagnating" ? (
            <p className="mt-3 flex items-center gap-2 text-sm text-clinical-warning">
              <AlertTriangle className="h-4 w-4" /> Progress is slower than configured expectation.
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            {openAlert ? <Button variant="secondary" onClick={() => acknowledge.mutate(openAlert.id)}>Review / acknowledge alert</Button> : null}
            <Button onClick={() => reassess.mutate()} disabled={reassess.isPending}>Request Intervention Reassessment</Button>
            <Link href={`/children/${d.id}/visits/new`}><Button variant="secondary">Record visit</Button></Link>
            <Link href={`/children/${d.id}/report`}><Button variant="ghost">Print summary</Button></Link>
          </div>
          {reassess.data ? <p className="mt-3 text-sm text-muted">{(reassess.data as { message?: string }).message ?? "Reassessment request stored."}</p> : null}
        </div>
      </section>

      {openAlert ? (
        <Card className="border-amber-200">
          <CardHeader><CardTitle>Recommended workflow action</CardTitle></CardHeader>
          <CardBody className="space-y-2 text-sm">
            <p className="font-medium">Progress requires review.</p>
            <p className="text-muted">
              Reason: {openAlert.message}. Suggested system action: request intervention reassessment.
              This is a workflow action, not a medical treatment instruction.
            </p>
            <div className="flex gap-3">
              <Button onClick={() => reassess.mutate()}>Request Reassessment</Button>
              <Button variant="secondary" onClick={() => acknowledge.mutate(openAlert.id)}>Acknowledge Alert</Button>
              <Button variant="ghost" onClick={() => setTab("Clinical Notes")}>Add Clinical Note</Button>
            </div>
          </CardBody>
        </Card>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {TABS.map((name) => (
          <button key={name} onClick={() => setTab(name)} className={`rounded-full border px-3 py-1.5 text-sm ${tab === name ? "border-teal-800 bg-teal-50" : "border-line bg-white"}`}>
            {name}
          </button>
        ))}
      </div>

      {tab === "Overview" ? (
        <Card>
          <CardBody className="pt-6">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chart}>
                  <XAxis dataKey="date" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="risk" stroke="#0F766E" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-3 text-xs text-muted">{PRODUCT.disclaimer}</p>
          </CardBody>
        </Card>
      ) : null}

      {tab === "Visit History" ? (
        <ol className="space-y-4">
          {d.visits.map((v) => (
            <li key={v.id} className="rounded-2xl border border-line bg-white p-5 shadow-card">
              <p className="text-sm text-muted">Visit {v.visit_number} · {new Date(v.visit_date).toLocaleDateString()}</p>
              <div className="mt-2 flex flex-wrap gap-3">
                <StatusBadge value={v.prediction?.status} />
                <StatusBadge value={v.prediction?.severity} />
                <StatusBadge value={v.progress} />
                <span className="text-sm">Risk {formatPercent(v.prediction?.risk)}</span>
              </div>
            </li>
          ))}
        </ol>
      ) : null}

      {tab === "Progress & Trajectory" ? <TrajectoryPanel visits={d.visits} warning={d.model_warning} /> : null}

      {tab === "Risk Factors" ? (
        <EmptyState title="Explainability component not connected" body="Component 2 owns advanced explanations. Component 1 shows prediction confidence and data quality only." />
      ) : null}

      {tab === "Alerts" ? (
        <ul className="space-y-3">
          {d.alerts.length === 0 ? <EmptyState title="No alerts require your attention." /> : d.alerts.map((a) => (
            <li key={a.id} className="rounded-2xl border border-line bg-white p-5">
              <div className="flex justify-between gap-3">
                <div>
                  <p className="font-medium">{a.message}</p>
                  <p className="text-sm text-muted">{a.type} · {a.severity}</p>
                </div>
                <StatusBadge value={a.status} />
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {tab === "Clinical Notes" ? (
        <Card>
          <CardBody className="space-y-4 pt-6">
            <p className="text-sm text-muted">Clinical notes are never sent to the prediction model.</p>
            <Textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a clinical note" />
            <Button onClick={() => addNote.mutate()} disabled={!note || addNote.isPending}>Save note</Button>
            {d.notes.map((n) => (
              <article key={n.id} className="rounded-xl bg-canvas p-3 text-sm">
                <p>{n.body}</p>
                <p className="mt-1 text-xs text-muted">{new Date(n.created_at).toLocaleString()}</p>
              </article>
            ))}
          </CardBody>
        </Card>
      ) : null}

      {tab === "Model Information" ? (
        <Card>
          <CardBody className="space-y-2 pt-6 text-sm">
            <p className="flex items-center gap-2"><Cpu className="h-4 w-4" /> Architecture: four modality encoders → multi-head cross-attention → type, severity and calibrated risk heads.</p>
            <p>Active model: {pred?.model ?? "MCA-2026-001"}</p>
            <p>Mode: {pred?.mode ?? "DEMO"}</p>
            <p>Confidence: {pred?.confidence ?? "—"}</p>
            <DemoBanner compact />
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}

function TrajectoryPanel({ visits, warning }: { visits: Profile["visits"]; warning?: string | null }) {
  const pts = visits.filter((v) => v.projection);
  const xs = pts.map((p) => p.projection!.x);
  const ys = pts.map((p) => p.projection!.y);
  const minX = Math.min(...xs, -1);
  const maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, -1);
  const maxY = Math.max(...ys, 1);
  const sx = (x: number) => ((x - minX) / (maxX - minX || 1)) * 520 + 40;
  const sy = (y: number) => 260 - ((y - minY) / (maxY - minY || 1)) * 200;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Multimodal latent trajectory</CardTitle>
        <p className="text-sm text-muted">This visualization represents changes in the model&apos;s learned multidimensional representation. It does not independently determine clinical status.</p>
      </CardHeader>
      <CardBody>
        {warning ? <p className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-clinical-warning">{warning}</p> : null}
        <svg viewBox="0 0 600 300" className="w-full rounded-xl bg-canvas" role="img" aria-label="Latent trajectory scatter">
          <text x="16" y="24" className="fill-muted" fontSize="11">Higher risk region (visual only)</text>
          {pts.map((p, i) => {
            const x = sx(p.projection!.x);
            const y = sy(p.projection!.y);
            const next = pts[i + 1];
            return (
              <g key={p.id}>
                {next ? <line x1={x} y1={y} x2={sx(next.projection!.x)} y2={sy(next.projection!.y)} stroke="#0F766E" strokeWidth="2" /> : null}
                <circle cx={x} cy={y} r="7" fill="#0F766E">
                  <title>{`Visit V${p.visit_number}\n${new Date(p.visit_date).toLocaleDateString()}\nRisk ${formatPercent(p.prediction?.risk)}\n${p.prediction?.status}`}</title>
                </circle>
                <text x={x + 10} y={y - 8} fontSize="11">V{p.visit_number}</text>
              </g>
            );
          })}
        </svg>
      </CardBody>
    </Card>
  );
}
