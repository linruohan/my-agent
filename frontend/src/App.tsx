import { lazy, Suspense, useState } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { ChatPane } from "@/components/ChatPane";
import { Composer } from "@/components/Composer";
import { ApprovalDialog } from "@/components/ApprovalDialog";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useAppStore } from "@/stores/app-store";

const SettingsModal = lazy(() =>
  import("@/components/SettingsModal").then((m) => ({ default: m.SettingsModal })),
);
const SkillsPanel = lazy(() =>
  import("@/components/SkillsPanel").then((m) => ({ default: m.SkillsPanel })),
);
const CalendarPanel = lazy(() =>
  import("@/components/CalendarPanel").then((m) => ({ default: m.CalendarPanel })),
);
const KnowledgePanel = lazy(() =>
  import("@/components/KnowledgePanel").then((m) => ({ default: m.KnowledgePanel })),
);
const TasksPanel = lazy(() =>
  import("@/components/TasksPanel").then((m) => ({ default: m.TasksPanel })),
);

function PanelFallback() {
  return (
    <div className="flex flex-1 items-center justify-center text-body text-muted-foreground">
      加载中…
    </div>
  );
}

export function App() {
  const ready = useAppStore((s) => s.ready);
  const bootError = useAppStore((s) => s.bootError);
  const activeView = useAppStore((s) => s.activeView);
  const [newTaskOpen, setNewTaskOpen] = useState(false);

  if (bootError) {
    return (
      <div className="flex h-full items-center justify-center bg-app-shell p-8">
        <div className="max-w-lg rounded-xl border border-surface-border bg-surface p-6 shadow-[var(--surface-shadow)]">
          <h1 className="text-title-sm font-semibold text-foreground">UI 启动失败</h1>
          <p className="mt-3 text-body text-muted-foreground">{bootError}</p>
          <p className="mt-2 text-caption text-muted-foreground">
            可设置 AGENT_UI=legacy 回退到旧版 legacy/web/index.html
          </p>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center bg-app-shell text-body text-muted-foreground">
        正在连接 pywebview…
      </div>
    );
  }

  return (
    <>
      <AppShell>
        {activeView === "chat" ? (
          <>
            <ChatPane />
            <Composer />
          </>
        ) : null}
        <Suspense fallback={<PanelFallback />}>
          {activeView === "tasks" ? (
            <TasksPanel newOpen={newTaskOpen} onNewOpenChange={setNewTaskOpen} />
          ) : null}
          {activeView === "skills" ? <SkillsPanel /> : null}
          {activeView === "calendar" ? <CalendarPanel /> : null}
          {activeView === "knowledge" ? <KnowledgePanel /> : null}
        </Suspense>
      </AppShell>
      <ApprovalDialog />
      <ConfirmDialog />
      <Suspense fallback={null}>
        <SettingsModal />
      </Suspense>
    </>
  );
}
