"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, persistCsrf, PRODUCT } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/field";
import { ArrowRight, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("phm@demo.local");
  const [password, setPassword] = useState("DemoPass123!");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const session = await api<{ csrf_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, remember_me: remember }),
      });
      persistCsrf(session.csrf_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-teal-900 p-12 text-white lg:flex lg:flex-col justify-between">
        <div className="absolute inset-0 opacity-30" style={{ background: "radial-gradient(circle at 20% 20%, #2dd4bf, transparent 40%), radial-gradient(circle at 80% 80%, #38bdf8, transparent 35%)" }} />
        <div className="relative">
          <p className="text-sm uppercase tracking-[0.2em] text-teal-100">Component 1 · J26-IT-399</p>
          <h1 className="mt-4 max-w-md text-4xl font-semibold leading-tight">{PRODUCT.name}</h1>
          <p className="mt-4 max-w-md text-lg text-teal-50">{PRODUCT.tagline}</p>
        </div>
        <ol className="relative grid grid-cols-4 gap-3 text-sm">
          {PRODUCT.workflow.map((step, i) => (
            <li key={step} className="rounded-2xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm">
              <p className="text-xs text-teal-100">0{i + 1}</p>
              <p className="mt-2 font-medium">{step}</p>
            </li>
          ))}
        </ol>
        <p className="relative text-sm text-teal-100">{PRODUCT.disclaimer}</p>
      </section>
      <section className="flex items-center justify-center p-6">
        <form onSubmit={onSubmit} className="w-full max-w-md rounded-2xl border border-line bg-white p-8 shadow-card">
          <h2 className="text-2xl font-semibold">Staff sign in</h2>
          <p className="mt-1 text-sm text-muted">Use your facility email or staff ID.</p>
          <div className="mt-6">
            <Label htmlFor="email">Email / staff ID</Label>
            <Input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="mt-4">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Remember me on this workstation
          </label>
          {error ? <p className="mt-3 text-sm text-clinical-danger">{error}</p> : null}
          <Button className="mt-6 w-full" type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"} <ArrowRight className="h-4 w-4" />
          </Button>
          <p className="mt-3 text-center text-sm text-muted">Password reset is handled by your facility administrator.</p>
          <div className="mt-6 flex items-start gap-2 rounded-xl bg-canvas p-3 text-xs text-muted">
            <ShieldCheck className="mt-0.5 h-4 w-4 text-teal-800" />
            Authorized health workers only. Sessions are audited. Do not share credentials. This is a research prototype, not an autonomous diagnosis system.
          </div>
        </form>
      </section>
    </div>
  );
}
