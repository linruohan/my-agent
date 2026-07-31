import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
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
  MoreHorizontal,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { useAppStore, type MainView } from "@/stores/app-store";
import { getApi } from "@/bridge/api";
import { SidebarSessions } from "@/components/shell/SidebarSessions";
import { GlobalSearch } from "@/components/shell/GlobalSearch";
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
  const [inboxMenu, setInboxMenu] = useState<{ x: number; y: number } | null>(null);
  const inboxMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 从其它视图进入 Inbox 时展开；已在 Inbox 内点击由自身切换折叠
    if (activeView === "chat") setInboxOpen(true);
  }, [activeView]);

  useEffect(() => {
    if (!inboxMenu) return;
    const onDoc = (e: MouseEvent) => {
      if (!inboxMenuRef.current?.contains(e.target as Node)) setInboxMenu(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setInboxMenu(null);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [inboxMenu]);

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

  const onNewSession = async () => {
    setInboxMenu(null);
    setActiveView("chat");
    setInboxOpen(true);
    const api = getApi();
    if (!api) return;
    const res = await api.new_session();
    if (!res?.ok) {
      if (res?.error) window.alert(res.error);
      return;
    }
    if (res.sessions) setSessions((res.sessions || []).filter((s) => !!s?.id));
    if ("events" in res) {
      useAppStore.getState().loadHistory(res.events || []);
    }
  };

  const onRefreshSessions = async () => {
    setInboxMenu(null);
    const api = getApi();
    if (!api?.list_sessions) return;
    try {
      const res = await api.list_sessions();
      if (res?.sessions) setSessions((res.sessions || []).filter((s) => !!s?.id));
    } catch (err) {
      console.warn("list_sessions failed:", err);
    }
  };

  const openInboxMenu = (el: HTMLElement) => {
    const rect = el.getBoundingClientRect();
    const pad = 8;
    const w = 160;
    const x = Math.min(rect.left, window.innerWidth - w - pad);
    const y = Math.min(rect.bottom + 4, window.innerHeight - 120);
    setInboxMenu({ x: Math.max(pad, x), y: Math.max(pad, y) });
  };

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-200",
        collapsed ? "w-12" : "w-64",
      )}
    >
      {/* 顶部：折叠 + 全局搜索 */}
      <div
        className={cn(
          "flex shrink-0 items-center gap-1.5 px-2 pt-3",
          collapsed && "flex-col px-1.5",
        )}
      >
        <button
          type="button"
          onClick={() => toggleSidebarCollapsed()}
          title={collapsed ? "展开侧栏" : "折叠侧栏"}
          className="flex size-8 shrink-0 items-center justify-center rounded-lg text-faint-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          {collapsed ? (
            <PanelLeft className="size-4" strokeWidth={1.75} />
          ) : (
            <PanelLeftClose className="size-4" strokeWidth={1.75} />
          )}
        </button>
        <GlobalSearch collapsed={collapsed} />
      </div>

      {/* 导航 + Inbox 会话层级 */}
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
                <div
                  className={cn(
                    "group/inbox flex items-center gap-0.5 rounded-lg",
                    active && "bg-sidebar-accent",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => {
                      if (activeView === "chat") {
                        setInboxOpen((v) => !v);
                      } else {
                        setActiveView("chat");
                        setInboxOpen(true);
                      }
                    }}
                    title={label}
                    className={cn(
                      "flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2.5 py-2 text-body transition",
                      active
                        ? "font-medium text-sidebar-accent-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                    )}
                  >
                    <Icon className="size-4 shrink-0" strokeWidth={1.75} />
                    <span className="truncate">{label}</span>
                  </button>

                  {/* 悬停显示：+ 新建 · … 更多 */}
                  <div
                    className={cn(
                      "mr-1 flex shrink-0 items-center gap-0.5 transition",
                      inboxMenu
                        ? "opacity-100"
                        : "opacity-0 group-hover/inbox:opacity-100 focus-within:opacity-100",
                    )}
                  >
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void onNewSession();
                      }}
                      className="rounded-md p-1 text-faint-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                      title="新建会话 (Ctrl+N)"
                      aria-label="新建会话"
                    >
                      <Plus className="size-3.5" strokeWidth={2} />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openInboxMenu(e.currentTarget);
                      }}
                      className={cn(
                        "rounded-md p-1 text-faint-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                        inboxMenu && "bg-sidebar-accent text-sidebar-accent-foreground",
                      )}
                      title="更多"
                      aria-label="更多"
                      aria-expanded={!!inboxMenu}
                    >
                      <MoreHorizontal className="size-3.5" strokeWidth={2} />
                    </button>
                  </div>
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
                if (isInbox) {
                  setInboxOpen(true);
                }
              }}
              onDoubleClick={() => {
                if (isInbox) void onNewSession();
              }}
              title={isInbox && collapsed ? "Inbox（双击新建）" : label}
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

      {/* 底部：工作区 + 设置按钮 */}
      <div
        className={cn(
          "mt-auto flex shrink-0 items-center gap-1 border-t border-sidebar-accent/80 px-2 py-2",
          collapsed && "flex-col px-1.5",
        )}
      >
        <button
          type="button"
          onClick={() => void onPickWorkDir()}
          className={cn(
            "flex min-w-0 flex-1 items-center rounded-lg text-left transition hover:bg-sidebar-accent",
            collapsed ? "justify-center p-2" : "gap-2 px-2 py-1.5",
          )}
          title="选择工作目录"
        >
          <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-brand text-micro font-semibold text-brand-foreground">
            {(workspace?.owner_name || "A").slice(0, 1)}
          </div>
          {!collapsed ? (
            <div className="min-w-0 flex-1">
              <div className="truncate text-label font-medium">
                {workspace?.owner_name || "个人助理"}
              </div>
              <div className="truncate text-micro text-muted-foreground">
                {workspace?.work_dir_label || "选择工作目录"}
              </div>
            </div>
          ) : null}
        </button>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          title="Settings"
          className="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <Settings className="size-4" strokeWidth={1.75} />
        </button>
      </div>

      {inboxMenu
        ? createPortal(
            <div
              ref={inboxMenuRef}
              role="menu"
              className="fixed z-[80] min-w-[156px] overflow-hidden rounded-lg border border-surface-border bg-surface py-1 shadow-[var(--menu-shadow)]"
              style={{ left: inboxMenu.x, top: inboxMenu.y }}
            >
              <button
                type="button"
                role="menuitem"
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-label text-foreground hover:bg-surface-hover"
                onClick={() => void onNewSession()}
              >
                <Plus className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                新建会话
              </button>
              <button
                type="button"
                role="menuitem"
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-label text-foreground hover:bg-surface-hover"
                onClick={() => {
                  setInboxMenu(null);
                  setInboxOpen((v) => !v);
                }}
              >
                {inboxOpen ? (
                  <ChevronDown className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                ) : (
                  <ChevronRight className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                )}
                {inboxOpen ? "收起会话列表" : "展开会话列表"}
              </button>
              <button
                type="button"
                role="menuitem"
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-label text-foreground hover:bg-surface-hover"
                onClick={() => void onRefreshSessions()}
              >
                <RefreshCw className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                刷新列表
              </button>
            </div>,
            document.body,
          )
        : null}
    </aside>
  );
}
