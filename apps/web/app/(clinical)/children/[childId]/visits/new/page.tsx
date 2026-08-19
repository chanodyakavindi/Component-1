"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/field";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { DemoBanner } from "@/components/demo-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatPercent, formatStatus } from "@/lib/utils";

const STEPS = ["Visit details", "Anthropometry", "Socioeconomic", "Dietary", "Maternal / child health", "Data quality"];

export default function NewVisitPage() {
  const { childId } = useParams<{ childId: string }>();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stages, setStages] = useState<string[]>([]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState({
    visit_date: new Date().toISOString().slice(0, 16),
    visit_type: "follow_up",
    scheduled: true,
    household_changed: false,
    age_months: 18,
    sex: "female",
    height_cm: 78,
    weight_kg: 9.1,
    muac_cm: 12.4,
    birth_weight_kg: 2.7,
    wealth_proxy: "second",
    maternal_education: "secondary",
    paternal_education: "primary",
    maternal_employment: "home",
    household_size: 5,
    geographical_area: "colombo",
    drinking_water: "piped",
    sanitation: "improved",
    breastfeeding_status: "continued",
    complementary_feeding: true,
    dietary_diversity_score: 4,
    meal_frequency: 3,
    micronutrient_supplementation: true,
    maternal_bmi: 21,
    gestational_age_weeks: 38,
    immunization_uptodate: true,
    vitamin_a: true,
    recent_diarrhoea: false,
    recent_respiratory_illness: false,
    recent_hospitalization: false,
    confirmation: false,
  });

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setStages(["Validating Data"]);
    try {
      await new Promise((r) => setTimeout(r, 300));
      setStages((s) => [...s, "Preparing Modalities"]);
      const payload = {
        visit_date: new Date(form.visit_date).toISOString(),
        visit_type: form.visit_type,
        scheduled: form.scheduled,
        confirmation_attested: form.confirmation,
        anthropometric: {
          age_months: Number(form.age_months),
          sex: form.sex,
          height_cm: Number(form.height_cm),
          weight_kg: Number(form.weight_kg),
          muac_cm: Number(form.muac_cm),
          birth_weight_kg: Number(form.birth_weight_kg),
        },
        socioeconomic: {
          household_changed: form.household_changed,
          wealth_proxy: form.wealth_proxy,
          maternal_education: form.maternal_education,
          paternal_education: form.paternal_education,
          maternal_employment: form.maternal_employment,
          household_size: Number(form.household_size),
          geographical_area: form.geographical_area,
          drinking_water: form.drinking_water,
          sanitation: form.sanitation,
        },
        dietary: {
          breastfeeding_status: form.breastfeeding_status,
          complementary_feeding: form.complementary_feeding,
          dietary_diversity_score: Number(form.dietary_diversity_score),
          meal_frequency: Number(form.meal_frequency),
          food_groups: ["grains", "dairy", "legumes"],
          micronutrient_supplementation: form.micronutrient_supplementation,
        },
        maternal_child_health: {
          maternal_bmi: Number(form.maternal_bmi),
          gestational_age_weeks: Number(form.gestational_age_weeks),
          immunization_uptodate: form.immunization_uptodate,
          vitamin_a: form.vitamin_a,
          recent_diarrhoea: form.recent_diarrhoea,
          recent_respiratory_illness: form.recent_respiratory_illness,
          recent_hospitalization: form.recent_hospitalization,
        },
      };
      await new Promise((r) => setTimeout(r, 250));
      setStages((s) => [...s, "Running Multimodal Model"]);
      const created = await api<{ visit: { id: string }; prediction: Record<string, unknown>; quality: Record<string, unknown> }>(
        `/children/${childId}/visits`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      setStages((s) => [...s, "Calibrating Risk", "Updating Longitudinal Profile"]);
      setResult(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Visit could not be saved");
    } finally {
      setBusy(false);
    }
  }

  if (result?.prediction) {
    const p = result.prediction as { status: string; severity: string; risk: number; confidence?: string; mode: string };
    return (
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Nutritional assessment</CardTitle>
        </CardHeader>
        <CardBody className="space-y-3">
          <DemoBanner />
          <p>Predicted status <strong>{formatStatus(p.status)}</strong></p>
          <p>Severity <StatusBadge value={p.severity} /></p>
          <p>Estimated risk <strong>{formatPercent(p.risk)}</strong></p>
          <p>Confidence {p.confidence ?? "moderate"}</p>
          <p>Model MCA-2026-001</p>
          <p className="text-sm text-muted">AI-assisted decision support — clinical review required.</p>
          <Button onClick={() => router.push(`/children/${childId}`)}>Open child profile</Button>
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold">New clinic visit</h1>
      <ol className="flex flex-wrap gap-2 text-xs">
        {STEPS.map((label, i) => (
          <li key={label} className={`rounded-full px-3 py-1 ${i === step ? "bg-teal-800 text-white" : "bg-white border border-line"}`}>{i + 1}. {label}</li>
        ))}
      </ol>
      <Card>
        <CardBody className="space-y-4 pt-6">
          {step === 0 ? (
            <>
              <Label>Visit date/time</Label>
              <Input type="datetime-local" value={form.visit_date} onChange={(e) => set("visit_date", e.target.value)} />
              <Label>Visit type</Label>
              <Select value={form.visit_type} onChange={(e) => set("visit_type", e.target.value)}>
                <option value="follow_up">Follow-up</option>
                <option value="routine">Routine</option>
                <option value="unscheduled">Unscheduled</option>
              </Select>
            </>
          ) : null}
          {step === 1 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {(["age_months", "height_cm", "weight_kg", "muac_cm", "birth_weight_kg"] as const).map((key) => (
                <div key={key}>
                  <Label>{key.replaceAll("_", " ")}</Label>
                  <Input type="number" step="0.1" value={form[key] as number} onChange={(e) => set(key, Number(e.target.value))} />
                </div>
              ))}
              <div>
                <Label>Sex</Label>
                <Select value={form.sex} onChange={(e) => set("sex", e.target.value)}>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </Select>
              </div>
            </div>
          ) : null}
          {step === 2 ? (
            <>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.household_changed} onChange={(e) => set("household_changed", e.target.checked)} />
                Has household information changed since the previous visit?
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                <div><Label>Wealth proxy</Label><Input value={form.wealth_proxy} onChange={(e) => set("wealth_proxy", e.target.value)} /></div>
                <div><Label>Maternal education</Label><Input value={form.maternal_education} onChange={(e) => set("maternal_education", e.target.value)} /></div>
                <div><Label>Household size</Label><Input type="number" value={form.household_size} onChange={(e) => set("household_size", Number(e.target.value))} /></div>
                <div><Label>Drinking water</Label><Input value={form.drinking_water} onChange={(e) => set("drinking_water", e.target.value)} /></div>
              </div>
            </>
          ) : null}
          {step === 3 ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div><Label>Breastfeeding</Label><Input value={form.breastfeeding_status} onChange={(e) => set("breastfeeding_status", e.target.value)} /></div>
              <div><Label>Dietary diversity</Label><Input type="number" value={form.dietary_diversity_score} onChange={(e) => set("dietary_diversity_score", Number(e.target.value))} /></div>
              <div><Label>Meal frequency</Label><Input type="number" value={form.meal_frequency} onChange={(e) => set("meal_frequency", Number(e.target.value))} /></div>
            </div>
          ) : null}
          {step === 4 ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div><Label>Maternal BMI</Label><Input type="number" value={form.maternal_bmi} onChange={(e) => set("maternal_bmi", Number(e.target.value))} /></div>
              <div><Label>Gestational age (weeks)</Label><Input type="number" value={form.gestational_age_weeks} onChange={(e) => set("gestational_age_weeks", Number(e.target.value))} /></div>
            </div>
          ) : null}
          {step === 5 ? (
            <div className="space-y-3 text-sm">
              <p>✓ Required fields complete</p>
              <p>✓ Valid measurement ranges (configured policy)</p>
              <p>⚠ Optional fields may be unavailable</p>
              <label className="flex items-start gap-2">
                <input type="checkbox" checked={form.confirmation} onChange={(e) => set("confirmation", e.target.checked)} />
                I confirm that the entered information matches the available clinic record.
              </label>
            </div>
          ) : null}
          {error ? <p className="text-sm text-clinical-danger">{typeof error === "string" ? error : JSON.stringify(error)}</p> : null}
          {stages.length > 0 ? (
            <ul className="text-sm">{stages.map((s) => <li key={s}>✓ {s}</li>)}</ul>
          ) : null}
          <div className="flex justify-between">
            <Button variant="secondary" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>Back</Button>
            {step < 5 ? <Button onClick={() => setStep((s) => s + 1)}>Continue</Button> : <Button onClick={submit} disabled={busy || !form.confirmation}>{busy ? "Running model…" : "Submit and predict"}</Button>}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
