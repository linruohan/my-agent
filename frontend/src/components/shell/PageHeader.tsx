import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { useAppStore, type MainView } from "@/stores/app-store";
import { cn } from "@/lib/cn";

const VIEW_LABEL: Record<MainView, string> = {
  chat: "Inbox",
  tasks: "Tasks",
  skills: "Skills",
  knowledge: "Knowledge",
  calendar: "Calendar",
};

type Props = {
  actions?: ReactNode;
  toolbar?: ReactNode;
};

export function PageHeader({ actions, toolbar }: Props) {
  const workspace = useAppStore((s) => s.workspace);
  const activeView = useAppStore((s) => s.activeView);
  const sessions = useAppStore((s) => s.sessions);

  const workspaceName = workspace?.owner_name || "个人助理";
  const viewLabel = VIEW_LABEL[activeView];
  const sessionTitle =
    activeView === "chat" ? sessions.find((s) => s.active)?.title || null : null;

  return (
    <div className="shrink-0 border-b border-border bg-page-canvas">
      <header className="flex h-12 items-center justify-between gap-3 px-4">
        <nav className="flex min-w-0 items-center gap-1 text-body text-muted-foreground">
          <span className="truncate font-medium text-foreground">{workspaceName}</span>
          <ChevronRight className="size-3.5 shrink-0 text-faint-foreground" strokeWidth={1.75} />
          <span className="shrink-0">{viewLabel}</span>
          {sessionTitle ? (
            <>
              <ChevronRight className="size-3.5 shrink-0 text-faint-foreground" strokeWidth={1.75} />
              <span className="truncate text-foreground">{sessionTitle}</span>
            </>
          ) : null}
        </nav>
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      </header>
      {toolbar ? (
        <div className={cn("flex items-center gap-2 border-t border-border px-4 py-2")}>
          {toolbar}
        </div>
      ) : null}
    </div>
  );
}
