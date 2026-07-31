import { useEffect, useState } from "react";
import {
  Inbox,
  LayoutDashboard,
  Sparkles,
  BookOpen,
  CalendarDays,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Plus,
  ChevronDown,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { useAppStore, type MainView } from "@/stores/app-store";
import { getApi } from "@/bridge/api";
import { SidebarSessions } from "@/components/shell/SidebarSessions";
import { cn } from "@/lib/cn";

const NAV: { view: MainView; label: string; Icon: LucideIcon }[] = [
  { view: "chat", label: "Inbox", Icon: Inbox },
  { view: "tasks", label: "Tasks", Icon: LayoutDashboard },
  { view: "skills", label: "Skills", Icon: Sparkles },
  { view: "knowledge", label: "Knowledge", Icon: BookOpen },
  { view: "calendar", label: "Calendar", Icon: CalendarDays },
];

export function NavRail() {
  const workspace = useAppStore((s) => s.workspace);
  const setWorkspace = useAppStore((s) => s.setWorkspace);
  const activeView = useAppStore((s) => s.activeView);
  const setActiveView = useAppStore((s) => s.setActiveView);
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen);
  const setSessions = useAppStore((s) => s.setSessions);
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebarCollapsed = useAppStore((s) => s.toggleSidebarCollapsed);
  const [inboxOpen, setInboxOpen] = useState(true);

  useEffect(() => {
    if (activeView === "chat") setInboxOpen(true);
  }, [activeView]);

  const onPickWorkDir = async () => {
    const api = getApi();
    if (!api) return;
    const res = await api.pick_work_dir();
    if (!res.ok || res.cancelled) return;
    const current = useAppStore.getState().workspace;
    setWorkspace({
      owner_name: current?.owner_name || "个人助理",
      work_dir: res.work_dir || "",
      work_dir_label: res.work_dir_label || "",
    });
  };

  const onNew = async () => {
    setActiveView("chat");
    setInboxOpen(true);
    const api = getApi();
    if (!api) return;
    const res = await api.new_session();
    if (!res?.ok) {
      if (res?.error) window.alert(res.error);
      return;
    }
    if (res.sessions) setSessions(res.sessions);
  };

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-200",
        collapsed ? "w-12" : "w-64",
      )}
    >
      <div className={cn("flex flex-col gap-2 px-3 pt-3", collapsed && "items-center px-1.5")}>
        <button
          type="button"
          onClick={() => void onPickWorkDir()}
          className={cn(
            "flex w-full items-center rounded-lg text-left transition hover:bg-sidebar-accent",
            collapsed ? "justify-center p-2" : "gap-2.5 px-2 py-2",
          )}
          title="选择工作目录"
        >
          <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-brand text-micro font-semibold text-brand-foreground">
            {(workspace?.owner_name || "A").slice(0, 1)}
          </div>
          {!collapsed ? (
            <>
              <div className="min-w-0 flex-1">
                <div className="truncate text-body font-medium">
                  {workspace?.owner_name || "个人助理"}
                </div>
                <div className="truncate text-caption text-muted-foreground">
                  {workspace?.work_dir_label || "选择工作目录"}
                </div>
              </div>
              <ChevronDown className="size-3.5 shrink-0 text-faint-foreground" />
            </>
          ) : null}
        </button>

        <button
          type="button"
          onClick={() => void onNew()}
          className={cn(
            "inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary text-primary-foreground transition hover:bg-primary/90",
            collapsed ? "size-8" : "h-8 w-full px-3 text-label font-medium",
          )}
          title="新建对话 (Ctrl+N)"
        >
          <Plus className="size-4" strokeWidth={1.75} />
          {!collapsed ? <span>New</span> : null}
        </button>
      </div>

      <nav
        className={cn(
          "mt-3 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2",
          collapsed && "px-1.5",
        )}
      >
        {NAV.map(({ view, label, Icon }) => {
          const active = activeView === view;
          const isInbox = view === "chat";

          if (isInbox && !collapsed) {
            return (
              <div key={view} className="flex flex-col">
                <div className="flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveView("chat");
                      setInboxOpen(true);
                    }}
                    title={label}
                    className={cn(
                      "flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2.5 py-2 text-body transition",
                      active
                        ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                    )}
                  >
                    <Icon className="size-4 shrink-0" strokeWidth={1.75} />
                    <span className="truncate">{label}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setInboxOpen((v) => !v)}
                    className="rounded-md p-1.5 text-faint-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                    title={inboxOpen ? "收起会话" : "展开会话"}
                    aria-expanded={inboxOpen}
                  >
                    {inboxOpen ? (
                      <ChevronDown className="size-3.5" strokeWidth={2} />
                    ) : (
                      <ChevronRight className="size-3.5" strokeWidth={2} />
                    )}
                  </button>
                </div>
                {inboxOpen ? <SidebarSessions /> : null}
              </div>
            );
          }

          return (
            <button
              key={view}
              type="button"
              onClick={() => {
                setActiveView(view);
                if (isInbox) setInboxOpen(true);
              }}
              title={label}
              className={cn(
                "flex items-center rounded-lg text-body transition",
                collapsed ? "justify-center p-2" : "gap-2.5 px-2.5 py-2",
                active
                  ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
              )}
            >
              <Icon className="size-4 shrink-0" strokeWidth={1.75} />
              {!collapsed ? <span className="truncate">{label}</span> : null}
            </button>
          );
        })}
      </nav>

      <div className={cn("mt-auto flex flex-col gap-0.5 px-2 pb-3", collapsed && "px-1.5")}>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          title="Settings"
          className={cn(
            "flex items-center rounded-lg text-body text-muted-foreground transition hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
            collapsed ? "justify-center p-2" : "gap-2.5 px-2.5 py-2",
          )}
        >
          <Settings className="size-4 shrink-0" strokeWidth={1.75} />
          {!collapsed ? <span>Settings</span> : null}
        </button>
        <button
          type="button"
          onClick={() => toggleSidebarCollapsed()}
          title={collapsed ? "展开侧栏" : "折叠侧栏"}
          className={cn(
            "flex items-center rounded-lg text-caption text-faint-foreground transition hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
            collapsed ? "justify-center p-2" : "gap-2.5 px-2.5 py-1.5",
          )}
        >
          {collapsed ? (
            <PanelLeft className="size-4" strokeWidth={1.75} />
          ) : (
            <>
              <PanelLeftClose className="size-4" strokeWidth={1.75} />
              <span>折叠</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
