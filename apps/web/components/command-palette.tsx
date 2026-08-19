"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  if (!open) return null;
  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };
  return (
    <div className="fixed inset-0 z-50 bg-ink/20 p-8" onClick={() => setOpen(false)}>
      <div className="mx-auto max-w-lg overflow-hidden rounded-2xl border border-line bg-white shadow-card" onClick={(e) => e.stopPropagation()}>
        <Command label="Command palette">
          <Command.Input placeholder="Search child, visit, alerts…" className="min-h-12 w-full border-b border-line px-4 text-sm outline-none" />
          <Command.List className="max-h-80 overflow-auto p-2">
            <Command.Item onSelect={() => go("/children")} className="rounded-lg px-3 py-2 text-sm hover:bg-canvas">Search child</Command.Item>
            <Command.Item onSelect={() => go("/children/new")} className="rounded-lg px-3 py-2 text-sm hover:bg-canvas">Register child</Command.Item>
            <Command.Item onSelect={() => go("/alerts")} className="rounded-lg px-3 py-2 text-sm hover:bg-canvas">View alerts</Command.Item>
            <Command.Item onSelect={() => go("/children")} className="rounded-lg px-3 py-2 text-sm hover:bg-canvas">New visit (open a child first)</Command.Item>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
