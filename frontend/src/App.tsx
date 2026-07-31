import { lazy, Suspense, useState } from "react";
import { AppShell } from "@/components/shell/AppShell";
import { ChatPane } from "@/components/ChatPane";
import { Composer } from "@/components/Composer";
import { ChatWidthControl } from "@/components/ChatWidthControl";
import { ApprovalDialog } from "@/components/ApprovalDialog";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useAppStore } from "@/stores/app-store";
import { getApi } from "@/bridge/api";

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
    <div className="flex flex-1 items-center justify-center text-sm text-muted">
      加载中…
    </div>
  );
}

function InboxActions() {
  const setSessions = useAppStore((s) => s.setSessions);
  const setActiveView = useAppStore((s) => s.setActiveView);

  const onNew = async () => {
    setActiveView("chat");
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
    <>
      <button
        type="button"
        onClick={() => void onNew()}
        className="h-8 rounded-lg border border-surface-border bg-surface px-2.5 text-label text-foreground hover:bg-surface-hover"
      >
        新建对话
      </button>
      <ChatWidthControl />
    </>
  );
}

export function App() {
  const ready = useAppStore((s) => s.ready);
  const bootError = useAppStore((s) => s.bootError);
  const activeView = useAppStore((s) => s.activeView);
  const [newTaskOpen, setNewTaskOpen] = useState(false);
  const [taskCount, setTaskCount] = useState<number | null>(null);

  if (bootError) {
    return (
      <div className="flex h-full items-center justify-center bg-app p-8">
        <div className="max-w-lg rounded-[var(--radius-panel)] border border-border bg-panel p-6">
          <h1 className="text-lg font-semibold text-fg">UI 启动失败</h1>
          <p className="mt-3 text-sm text-muted">{bootError}</p>
          <p className="mt-2 text-xs text-muted">
            可设置 AGENT_UI=legacy 回退到旧版 web/index.html
          </p>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center bg-app text-sm text-muted">
        正在连接 pywebview…
      </div>
    );
  }

  const headerActions =
    activeView === "chat" ? (
      <InboxActions />
    ) : activeView === "tasks" ? (
      <>
        {taskCount != null ? (
          <span className="text-caption text-muted-foreground">{taskCount} Tasks</span>
        ) : null}
        <button
          type="button"
          onClick={() => setNewTaskOpen(true)}
          className="h-8 rounded-lg bg-primary px-2.5 text-label font-medium text-primary-foreground"
        >
          + New Task
        </button>
      </>
    ) : null;

  return (
    <>
      <AppShell headerActions={headerActions}>
        {activeView === "chat" ? (
          <>
            <ChatPane />
            <Composer />
          </>
        ) : null}
        <Suspense fallback={<PanelFallback />}>
          {activeView === "tasks" ? (
            <TasksPanel
              newOpen={newTaskOpen}
              onNewOpenChange={setNewTaskOpen}
              onCountChange={setTaskCount}
            />
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
