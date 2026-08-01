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

/**
 * NavRail - 左侧导航栏组件
 *
 * 功能：
 * - 主导航：Inbox / Tasks / Skills / Knowledge / Calendar
 * - 会话列表展开 / 折叠
 * - 工作区选择 & 设置入口
 * - 折叠/展开侧栏按钮
 * - 全局搜索入口
 * - Apple 风格：玻璃拟态 + Bento 大圆角 + Spring 微交互
 */
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

  /* 从其它视图进入 Inbox 时展开；已在 Inbox 内点击由自身切换折叠 */
  useEffect(() => {
    if (activeView === "chat") setInboxOpen(true);
  }, [activeView]);

  /* 点击外部关闭弹出菜单 */
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

  /**
   * 弹窗选择工作目录
   */
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

  /**
   * 新建会话并切换到聊天视图
   */
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

  /**
   * 刷新会话列表
   */
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

  /**
   * 打开 Inbox 弹出菜单（定位计算）
   */
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
        "relative flex h-full shrink-0 flex-col",
      )}
    >
      {/* 玻璃背景：Bento 风格独立玻璃卡片 */}
      <div
        className={cn(
          "absolute inset-y-3 inset-x-2 rounded-[22px]",
          "bg-sidebar/72 backdrop-blur-[32px] backdrop-saturate-180",
          "-webkit-backdrop-blur-[32px] -webkit-backdrop-saturate-180",
          "border border-sidebar-border/80",
          "shadow-[0_8px_28px_rgba(0,0,0,0.06),0_2px_8px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,0.8)]",
          "transition-all duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]",
          collapsed ? "left-1.5 right-1.5" : "left-2 right-2",
        )}
        style={{ backgroundColor: "var(--sidebar)" }}
      />

      {/* 内部内容容器 */}
      <div
        className={cn(
          "relative z-10 flex h-full flex-col text-sidebar-foreground transition-[width] duration-300 ease-[cubic-bezier(0.25,1,0.5,1)] animate-fade-in-left",
          collapsed ? "w-12 mx-1.5" : "w-64 mx-2",
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
            className="flex size-9 shrink-0 items-center justify-center rounded-[11px] text-muted-foreground/80
              transition-all duration-200 ease-[cubic-bezier(0.25,1,0.5,1)]
              hover:bg-brand/12 hover:text-brand
              hover:scale-[1.08] active:scale-[0.95]
              hover:shadow-[0_4px_12px_rgba(0,113,227,0.18)]"
          >
            {collapsed ? (
              <PanelLeft className="size-[18px]" strokeWidth={1.75} />
            ) : (
              <PanelLeftClose className="size-[18px]" strokeWidth={1.75} />
            )}
          </button>
          <GlobalSearch collapsed={collapsed} />
        </div>

        {/* 导航 + Inbox 会话层级 */}
        <nav
          className={cn(
            "mt-4 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-2",
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
                      "group/inbox flex items-center gap-0.5 rounded-[12px]",
                      "transition-all duration-200 ease-[cubic-bezier(0.25,1,0.5,1)]",
                      active && "bg-gradient-to-r from-brand/16 to-brand-purple/10",
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
                        "flex min-w-0 flex-1 items-center gap-2.5 rounded-[12px] px-2.5 py-2.5 text-[13.5px] font-medium transition-all duration-200",
                        active
                          ? "text-brand"
                          : "text-muted-foreground hover:bg-surface-hover/70 hover:text-foreground hover:translate-x-[1px]",
                      )}
                    >
                      <span
                        className={cn(
                          "flex size-[28px] items-center justify-center rounded-[8px] shrink-0",
                          "transition-all duration-200",
                          active
                            ? "bg-gradient-to-br from-brand to-brand-purple text-white shadow-[0_4px_12px_rgba(0,113,227,0.32)]"
                            : "bg-surface-hover/60",
                        )}
                      >
                        <Icon className="size-4" strokeWidth={active ? 2 : 1.75} />
                      </span>
                      <span className="truncate tracking-[-0.01em]">{label}</span>
                    </button>

                    {/* 悬停显示：+ 新建 · … 更多 */}
                    <div
                      className={cn(
                        "mr-1 flex shrink-0 items-center gap-0.5 transition-all duration-200",
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
                        className="rounded-[9px] p-1.5 text-muted-foreground/80
                          transition-all duration-200 ease-[cubic-bezier(0.34,1.56,0.64,1)]
                          hover:bg-brand/12 hover:text-brand
                          hover:scale-[1.12] active:scale-[0.95]"
                        title="新建会话 (Ctrl+N)"
                        aria-label="新建会话"
                      >
                        <Plus className="size-[16px]" strokeWidth={2.25} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          openInboxMenu(e.currentTarget);
                        }}
                        className={cn(
                          "rounded-[9px] p-1.5 transition-all duration-200 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
                          "hover:scale-[1.12] active:scale-[0.95]",
                          inboxMenu
                            ? "bg-brand/14 text-brand shadow-[0_4px_12px_rgba(0,113,227,0.2)]"
                            : "text-muted-foreground/80 hover:bg-surface-hover hover:text-foreground",
                        )}
                        title="更多"
                        aria-label="更多"
                        aria-expanded={!!inboxMenu}
                      >
                        <MoreHorizontal className="size-[16px]" strokeWidth={2.25} />
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
                  "flex items-center rounded-[12px] text-[13.5px] font-medium transition-all duration-200 ease-[cubic-bezier(0.25,1,0.5,1)]",
                  collapsed ? "justify-center p-2 my-0.5" : "gap-2.5 px-2.5 py-2.5",
                  active
                    ? "bg-gradient-to-r from-brand/14 to-brand-purple/9 text-brand translate-x-[1px]"
                    : "text-muted-foreground hover:bg-surface-hover/60 hover:text-foreground hover:translate-x-[1px]",
                )}
              >
                <span
                  className={cn(
                    "flex items-center justify-center rounded-[8px] shrink-0 transition-all duration-200",
                    collapsed ? "size-[30px]" : "size-[28px]",
                    active
                      ? "bg-gradient-to-br from-brand to-brand-purple text-white shadow-[0_4px_12px_rgba(0,113,227,0.3)]"
                      : "bg-surface-hover/60",
                  )}
                >
                  <Icon
                    className={collapsed ? "size-[18px]" : "size-4"}
                    strokeWidth={active ? 2 : 1.75}
                  />
                </span>
                {!collapsed ? (
                  <span className="truncate tracking-[-0.01em]">{label}</span>
                ) : null}
              </button>
            );
          })}
        </nav>

        {/* 底部：工作区 + 设置按钮 */}
        <div
          className={cn(
            "mt-auto flex shrink-0 items-center gap-1.5 border-t border-border/60 px-2 py-3",
            collapsed && "flex-col px-1.5",
          )}
        >
          <button
            type="button"
            onClick={() => void onPickWorkDir()}
            className={cn(
              "flex min-w-0 flex-1 items-center rounded-[12px] text-left",
              "transition-all duration-200 ease-[cubic-bezier(0.25,1,0.5,1)]",
              "hover:bg-surface-hover/70 hover:translate-y-[-1px]",
              collapsed ? "justify-center p-2" : "gap-2.5 px-2.5 py-2",
            )}
            title="选择工作目录"
          >
            <div
              className="flex size-[30px] shrink-0 items-center justify-center rounded-[9px]
                bg-gradient-to-br from-brand to-brand-purple text-[12px] font-bold text-white
                shadow-[0_4px_12px_rgba(0,113,227,0.3)]"
            >
              {(workspace?.owner_name || "A").slice(0, 1)}
            </div>
            {!collapsed ? (
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-semibold tracking-[-0.01em]">
                  {workspace?.owner_name || "个人助理"}
                </div>
                <div className="truncate text-[11px] text-muted-foreground mt-0.5">
                  {workspace?.work_dir_label || "选择工作目录"}
                </div>
              </div>
            ) : null}
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            title="Settings"
            className="flex size-9 shrink-0 items-center justify-center rounded-[11px] text-muted-foreground/80
              transition-all duration-200 ease-[cubic-bezier(0.34,1.56,0.64,1)]
              hover:bg-brand/12 hover:text-brand
              hover:scale-[1.1] active:scale-[0.95]
              hover:shadow-[0_4px_12px_rgba(0,113,227,0.18)]"
          >
            <Settings className="size-[18px]" strokeWidth={1.75} />
          </button>
        </div>
      </div>

      {/* Inbox 弹出菜单：Portal 到 body */}
      {inboxMenu
        ? createPortal(
            <div
              ref={inboxMenuRef}
              role="menu"
              className="fixed z-[80] min-w-[170px] overflow-hidden rounded-[16px]
                border border-surface-border/80 bg-surface/95
                backdrop-blur-[28px] backdrop-saturate-180
                -webkit-backdrop-blur-[28px] -webkit-backdrop-saturate-180
                py-1.5
                shadow-[0_20px_60px_rgba(0,0,0,0.15),0_8px_24px_rgba(0,0,0,0.1),0_0_0_0.5px_rgba(0,0,0,0.05)]
                animate-scale-in origin-top-left"
              style={{ left: inboxMenu.x, top: inboxMenu.y }}
            >
              {[
                {
                  label: "新建会话",
                  icon: Plus,
                  onClick: () => void onNewSession(),
                },
                {
                  label: inboxOpen ? "收起会话列表" : "展开会话列表",
                  icon: inboxOpen ? ChevronDown : ChevronRight,
                  onClick: () => {
                    setInboxMenu(null);
                    setInboxOpen((v) => !v);
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
                  className="group flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px]
                    text-foreground transition-all duration-150
                    hover:bg-brand/10 hover:text-brand hover:pl-4"
                >
                  <it.icon className="size-[15px] text-muted-foreground/90 group-hover:text-brand/80" strokeWidth={1.75} />
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
