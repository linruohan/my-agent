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

/**
 * AppShell - 应用主外壳组件
 *
 * 功能：
 * - 渲染左侧导航栏 NavRail
 * - 渲染主内容容器（含毛玻璃效果和 Bento 风格大圆角）
 * - 监听全局 Ctrl/⌘ + N 快捷键创建新会话
 * - 应用 Aurora 背景之上的层级定位
 */
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
          if ("events" in res) {
            useAppStore.getState().loadHistory(res.events || []);
          }
        })();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setActiveView, setSessions]);

  return (
    <div className="relative flex h-full w-full overflow-hidden bg-app-shell">
      {/* NavRail 左侧导航（Bento 风格玻璃卡片） */}
      <NavRail />

      {/* 主内容区：毛玻璃大卡片 + Bento 圆角 + 层级阴影 */}
      <div
        className={cn(
          "relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
          "my-3 mr-3 rounded-2xl bg-page-canvas",
          "border border-surface-border",
          "shadow-[0_12px_40px_rgba(0,0,0,0.08),0_4px_16px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,0.95)]",
          "backdrop-blur-[30px] backdrop-saturate-180",
          "-webkit-backdrop-blur-[30px] -webkit-backdrop-saturate-180",
          collapsed ? "ml-3" : "ml-0.5",
          "animate-fade-in-up",
        )}
        style={{ animationDelay: "60ms" }}
      >
        <PageHeader actions={headerActions} toolbar={headerToolbar} />
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </div>
  );
}
