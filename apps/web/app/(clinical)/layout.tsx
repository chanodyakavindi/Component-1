import { AppShell } from "@/components/app-shell";

export default function ClinicalLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
