"use client";

import { PRODUCT } from "@/lib/api";
import { AlertTriangle } from "lucide-react";

export function DemoBanner({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-clinical-warning">
      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
      <div>
        <p className="font-semibold tracking-wide">DEMO MODEL — NOT FOR CLINICAL USE</p>
        {!compact ? <p className="text-xs text-amber-800/80">{PRODUCT.disclaimer}</p> : null}
      </div>
    </div>
  );
}

export function ResearchDisclaimer() {
  return (
    <p className="rounded-xl border border-line bg-white px-4 py-3 text-sm text-muted">{PRODUCT.researchDisclaimer}</p>
  );
}
