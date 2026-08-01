import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
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
  MessageSquare,
  type LucideIcon,
} from "lucide-react";
import { useAppStore, type MainView } from "@/stores/app-store";
import { getApi } from "@/bridge/api";
import { SidebarSessions } from "@/components/shell/SidebarSessions";
import { GlobalSearch } from "@/components/shell/GlobalSearch";
import { cn } from "@/lib/cn";

const TOP_NAV: { view: MainView; label: string; Icon: LucideIcon }[] = [
  { view: "tasks", label: "Tasks", Icon: LayoutDashboard },
  { view: "skills", label: "Skills", Icon: Sparkles },
  { view: "knowledge", label: "Knowledge", Icon: BookOpen },
  { view: "calendar", label: "Calendar", Icon: CalendarDays },
];

function navItemClass(active: boolean, collapsed: boolean) {
  return cn(
    "flex items-center rounded-md text-body font-medium transition-colors",
    collapsed ? "justify-center p-2" : "gap-2 px-2 py-2",
    active
      ? "bg-sidebar-accent text-sidebar-accent-foreground"
      : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground",
  );
}

export function NavRail() {
  const workspace = useAppStore((s) => s.workspace);
  const setWorkspace = useAppStore((s) => s.setWorkspace);
  const activeView = useAppStore((s) => s.activeView);
  const setActiveView = useAppStore((s) => s.setActiveView);
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen);
  const setSessions = useAppStore((s) => s.setSessions);
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebarCollapsed = useAppStore((s) => s.toggleSidebarCollapsed);
  const [chatOpen, setChatOpen] = useState(true);
  const [chatMenu, setChatMenu] = useState<{ x: number; y: number } | null>(null);
  const chatMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeView === "chat") setChatOpen(true);
  }, [activeView]);

  useEffect(() => {
    if (!chatMenu) return;
    const onDoc = (e: MouseEvent) => {
      if (!chatMenuRef.current?.contains(e.target as Node)) setChatMenu(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setChatMenu(null);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [chatMenu]);

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
    setChatMenu(null);
    setActiveView("chat");
    setChatOpen(true);
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
    setChatMenu(null);
    const api = getApi();
    if (!api?.list_sessions) return;
    try {
      const res = await api.list_sessions();
      if (res?.sessions) setSessions((res.sessions || []).filter((s) => !!s?.id));
    } catch (err) {
      console.warn("list_sessions failed:", err);
    }
  };

  const openChatMenu = (el: HTMLElement) => {
    const rect = el.getBoundingClientRect();
    const pad = 8;
    const w = 160;
    const x = Math.min(rect.left, window.innerWidth - w - pad);
    const y = Math.min(rect.bottom + 4, window.innerHeight - 120);
    setChatMenu({ x: Math.max(pad, x), y: Math.max(pad, y) });
  };

  const chatActive = activeView === "chat";

  return (
    <aside
      className={cn(
        "relative flex h-full shrink-0 flex-col bg-sidebar text-sidebar-foreground",
        "transition-[width] duration-200",
        collapsed ? "w-12" : "w-64",
      )}
    >
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
          className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
        >
          {collapsed ? (
            <PanelLeft className="size-4" strokeWidth={1.75} />
          ) : (
            <PanelLeftClose className="size-4" strokeWidth={1.75} />
          )}
        </button>
        <GlobalSearch collapsed={collapsed} />
      </div>

      <nav
        className={cn(
          "mt-3 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2",
          collapsed && "px-1.5",
        )}
      >
        {TOP_NAV.map(({ view, label, Icon }) => {
          const active = activeView === view;
          return (
            <button
              key={view}
              type="button"
              onClick={() => setActiveView(view)}
              title={label}
              className={navItemClass(active, collapsed)}
            >
              <Icon
                className={collapsed ? "size-[18px]" : "size-4"}
                strokeWidth={active ? 2 : 1.75}
              />
              {!collapsed ? <span className="truncate">{label}</span> : null}
            </button>
          );
        })}

        {/* 聊天：紧接 Calendar 下方 */}
        {!collapsed ? (
          <div className="mt-0.5 flex min-h-0 flex-col">
            <div className="group/chat flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => {
                  if (activeView === "chat") {
                    setChatOpen((v) => !v);
                  } else {
                    setActiveView("chat");
                    setChatOpen(true);
                  }
                }}
                title="聊天"
                className={cn(navItemClass(chatActive, false), "min-w-0 flex-1")}
              >
                <MessageSquare
                  className="size-4 shrink-0"
                  strokeWidth={chatActive ? 2 : 1.75}
                />
                <span className="truncate">聊天</span>
              </button>
              <div
                className={cn(
                  "mr-0.5 flex shrink-0 items-center gap-0.5 transition-opacity",
                  chatMenu
                    ? "opacity-100"
                    : "opacity-0 group-hover/chat:opacity-100 focus-within:opacity-100",
                )}
              >
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    void onNewSession();
                  }}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
                  title="新建会话 (Ctrl+N)"
                  aria-label="新建会话"
                >
                  <Plus className="size-4" strokeWidth={2} />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    openChatMenu(e.currentTarget);
                  }}
                  className={cn(
                    "rounded-md p-1.5",
                    chatMenu
                      ? "bg-sidebar-accent text-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
                  )}
                  title="更多"
                  aria-label="更多"
                  aria-expanded={!!chatMenu}
                >
                  <MoreHorizontal className="size-4" strokeWidth={2} />
                </button>
              </div>
            </div>
            {chatOpen ? (
              <div className="min-h-0 flex-1 overflow-y-auto pb-1">
                <SidebarSessions />
              </div>
            ) : null}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => {
              setActiveView("chat");
              setChatOpen(true);
            }}
            onDoubleClick={() => void onNewSession()}
            title="聊天（双击新建）"
            className={navItemClass(chatActive, true)}
          >
            <MessageSquare
              className="size-[18px]"
              strokeWidth={chatActive ? 2 : 1.75}
            />
          </button>
        )}
      </nav>

      <div
        className={cn(
          "mt-auto flex shrink-0 items-center gap-1 border-t border-sidebar-border px-2 py-2.5",
          collapsed && "flex-col px-1.5",
        )}
      >
        <button
          type="button"
          onClick={() => void onPickWorkDir()}
          className={cn(
            "flex min-w-0 flex-1 items-center rounded-md text-left hover:bg-sidebar-accent",
            collapsed ? "justify-center p-2" : "gap-2 px-2 py-1.5",
          )}
          title="选择工作目录"
        >
          <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-caption font-semibold text-primary-foreground">
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
          className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
        >
          <Settings className="size-4" strokeWidth={1.75} />
        </button>
      </div>

      {chatMenu
        ? createPortal(
            <div
              ref={chatMenuRef}
              role="menu"
              className="fixed z-[80] min-w-[160px] overflow-hidden rounded-lg border border-surface-border bg-surface-raised py-1 shadow-[var(--menu-shadow)]"
              style={{ left: chatMenu.x, top: chatMenu.y }}
            >
              {[
                { label: "新建会话", icon: Plus, onClick: () => void onNewSession() },
                {
                  label: chatOpen ? "收起会话列表" : "展开会话列表",
                  icon: chatOpen ? ChevronDown : ChevronRight,
                  onClick: () => {
                    setChatMenu(null);
                    setChatOpen((v) => !v);
                  },
                },
                {
                  label: "刷新列表",
                  icon: RefreshCw,
                  onClick: () => void onRefreshSessions(),
                },
              ].map((it) => (
                <button
                  key={it.label}
                  type="button"
                  role="menuitem"
                  onClick={it.onClick}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-body text-foreground hover:bg-surface-hover"
                >
                  <it.icon className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                  {it.label}
                </button>
              ))}
            </div>,
            document.body,
          )
        : null}
    </aside>
  );
}
