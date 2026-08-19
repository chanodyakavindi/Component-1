"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Bell,
  ChevronLeft,
  ClipboardList,
  Cpu,
  LayoutDashboard,
  LogOut,
  Search,
  Settings,
  Shield,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import { api, PRODUCT } from "@/lib/api";
import { Button } from "./ui/button";
import { CommandPalette } from "./command-palette";
import { cn } from "@/lib/utils";

type User = {
  full_name: string;
  role: string;
  email: string;
  facility_name?: string;
  facility_code?: string;
};

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["*"] },
  { href: "/children", label: "Children", icon: Users, roles: ["system_admin", "facility_admin", "doctor", "health_worker", "nutritionist"] },
  { href: "/visits", label: "Visits", icon: ClipboardList, roles: ["system_admin", "facility_admin", "doctor", "health_worker", "nutritionist"] },
  { href: "/alerts", label: "Alerts", icon: Bell, roles: ["system_admin", "facility_admin", "doctor", "health_worker", "nutritionist"] },
  { href: "/analytics", label: "Analytics", icon: BarChart3, roles: ["*"] },
  { href: "/research/models", label: "Models", icon: Cpu, roles: ["system_admin", "researcher", "facility_admin"] },
  { href: "/reports", label: "Reports", icon: Activity, roles: ["*"] },
  { href: "/admin/system", label: "Admin", icon: Settings, roles: ["system_admin", "facility_admin"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [q, setQ] = useState("");
  const user = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/auth/me") });
  const notes = useQuery({ queryKey: ["notifications"], queryFn: () => api<{ items: { id: string; title: string; severity: string; created_at: string }[] }>("/notifications") });
  const logout = useMutation({
    mutationFn: () => api("/auth/logout", { method: "POST" }),
    onSuccess: () => router.push("/login"),
  });

  const items = useMemo(
    () => NAV.filter((n) => n.roles.includes("*") || (user.data && n.roles.includes(user.data.role))),
    [user.data],
  );

  if (user.isError) {
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-canvas">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 bg-white px-3 py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-white/90 backdrop-blur">
        <div className="flex h-16 items-center gap-4 px-4">
          <button className="rounded-lg p-2 hover:bg-canvas" onClick={() => setCollapsed((v) => !v)} aria-label="Collapse sidebar">
            <ChevronLeft className={cn("h-4 w-4 transition", collapsed && "rotate-180")} />
          </button>
          <div>
            <p className="text-sm font-semibold">{PRODUCT.name}</p>
            <p className="text-xs text-muted">{user.data?.facility_name ?? "Facility"}</p>
          </div>
          <form
            className="ml-6 hidden flex-1 items-center md:flex"
            onSubmit={(e) => {
              e.preventDefault();
              if (q) router.push(`/children?q=${encodeURIComponent(q)}`);
            }}
          >
            <div className="relative w-full max-w-xl">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search child ID or alerts"
                className="min-h-11 w-full rounded-xl border border-line bg-canvas pl-9 pr-3 text-sm"
              />
            </div>
          </form>
          <NotificationMenu items={notes.data?.items ?? []} />
          <div className="text-right text-sm">
            <p className="font-medium">{user.data?.full_name ?? "…"}</p>
            <p className="text-xs capitalize text-muted">{user.data?.role?.replace("_", " ")}</p>
          </div>
          <Button variant="ghost" onClick={() => logout.mutate()} aria-label="Log out">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>
      <div className="flex">
        <nav className={cn("min-h-[calc(100vh-4rem)] border-r border-line bg-white p-3 transition-all", collapsed ? "w-[72px]" : "w-60")} aria-label="Primary">
          <ul className="space-y-1">
            {items.map((item) => {
              const active = pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={cn(
                      "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm",
                      active ? "bg-teal-50 text-teal-900 font-medium" : "text-ink hover:bg-canvas",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {!collapsed ? item.label : <span className="sr-only">{item.label}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
          <div className="mt-8 px-3 text-[11px] leading-snug text-muted">
            {!collapsed ? PRODUCT.disclaimer : null}
          </div>
        </nav>
        <main id="main" className="min-w-0 flex-1 p-6">
          {children}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

function NotificationMenu({ items }: { items: { id: string; title: string; severity: string; created_at: string }[] }) {
  const [open, setOpen] = useState(false);
  const critical = items.filter((i) => i.severity === "HIGH" || i.severity === "URGENT");
  return (
    <div className="relative">
      <button className="relative rounded-lg p-2 hover:bg-canvas" onClick={() => setOpen((v) => !v)} aria-label="Notifications">
        <Bell className="h-5 w-5" />
        {items.length > 0 ? <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-clinical-danger" /> : null}
      </button>
      {open ? (
        <div className="absolute right-0 mt-2 w-80 rounded-2xl border border-line bg-white p-3 shadow-card">
          <p className="px-2 text-xs font-semibold uppercase text-muted">Critical</p>
          {critical.length === 0 ? <p className="px-2 py-3 text-sm text-muted">No critical alerts require your attention.</p> : null}
          {critical.slice(0, 4).map((n) => (
            <p key={n.id} className="rounded-lg px-2 py-2 text-sm hover:bg-canvas">{n.title}</p>
          ))}
          <p className="mt-2 px-2 text-xs font-semibold uppercase text-muted">Today</p>
          {items.slice(0, 6).map((n) => (
            <p key={n.id} className="rounded-lg px-2 py-2 text-sm hover:bg-canvas">{n.title}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
