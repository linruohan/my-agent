import { useEffect, type ReactNode } from "react";
import { NavRail } from "@/components/shell/NavRail";
import { PageHeader } from "@/components/shell/PageHeader";
import { useAppStore } from "@/stores/app-store";
import { getApi } from "@/bridge/api";
import { cn } from "@/lib/cn";

type Props = {
  headerActions?: ReactNode;
  headerToolbar?: ReactNode;
  children: ReactNode;
};

export function AppShell({ headerActions, headerToolbar, children }: Props) {
  const setActiveView = useAppStore((s) => s.setActiveView);
  const setSessions = useAppStore((s) => s.setSessions);
  const collapsed = useAppStore((s) => s.sidebarCollapsed);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === "n" || e.key === "N")) {
        const tag = (e.target as HTMLElement | null)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
        e.preventDefault();
        void (async () => {
          setActiveView("chat");
          const api = getApi();
          if (!api) return;
          const res = await api.new_session();
          if (!res?.ok) {
            if (res?.error) window.alert(res.error);
            return;
          }
          if (res.sessions) setSessions(res.sessions);
        })();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setActiveView, setSessions]);

  return (
    <div className="flex h-full bg-app-shell">
      <NavRail />
      <div
        className={cn(
          "relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
          "mb-2 mr-2 rounded-xl bg-page-canvas",
          "ring-1 ring-surface-border shadow-[var(--surface-shadow)]",
          collapsed ? "ml-2" : "ml-0.5",
        )}
      >
        <PageHeader actions={headerActions} toolbar={headerToolbar} />
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </div>
  );
}
