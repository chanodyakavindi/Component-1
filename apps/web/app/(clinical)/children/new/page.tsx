"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/field";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";

export default function RegisterChildPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setSaving(true);
    setError(null);
    try {
      const created = await api<{ id: string; pseudonymous_id: string }>("/children", {
        method: "POST",
        body: JSON.stringify({
          date_of_birth: form.get("dob"),
          sex: form.get("sex"),
          responsible_team: form.get("team"),
          external_patient_id: form.get("external") || null,
          caregiver_relationship: form.get("rel"),
          caregiver_display_name: form.get("caregiver") || null,
        }),
      });
      router.push(`/children/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register child");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Register child</CardTitle>
        <p className="text-sm text-muted">Collect only operationally necessary information. Names are not used as model features.</p>
      </CardHeader>
      <CardBody>
        <form onSubmit={onSubmit} className="grid gap-4">
          <div>
            <Label htmlFor="dob">Date of birth</Label>
            <Input id="dob" name="dob" type="date" required />
          </div>
          <div>
            <Label htmlFor="sex">Sex</Label>
            <Select id="sex" name="sex" required>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="intersex">Intersex</option>
              <option value="unknown">Unknown</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="team">Responsible clinic / team</Label>
            <Input id="team" name="team" placeholder="Clinic 04" />
          </div>
          <div>
            <Label htmlFor="external">External hospital ID (optional, stored encrypted)</Label>
            <Input id="external" name="external" />
          </div>
          <div className="border-t border-line pt-4">
            <p className="text-sm font-medium">Caregiver (operational only)</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <Label htmlFor="rel">Relationship</Label>
                <Input id="rel" name="rel" defaultValue="mother" />
              </div>
              <div>
                <Label htmlFor="caregiver">Display name (optional)</Label>
                <Input id="caregiver" name="caregiver" />
              </div>
            </div>
          </div>
          {error ? <p className="text-sm text-clinical-danger">{error}</p> : null}
          <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Create record"}</Button>
        </form>
      </CardBody>
    </Card>
  );
}
