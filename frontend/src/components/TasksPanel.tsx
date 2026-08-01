import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Circle,
  Clock3,
  AlertCircle,
  CheckCircle2,
  type LucideIcon,
} from "lucide-react";
import { getApi } from "@/bridge/api";
import type { TaskItem, TaskStatus } from "@/bridge/types";
import { confirmAction } from "@/stores/confirm-store";
import { cn } from "@/lib/cn";

const COLUMNS: {
  status: TaskStatus;
  title: string;
  Icon: LucideIcon;
  iconClass: string;
}[] = [
  { status: "pending", title: "Todo", Icon: Circle, iconClass: "text-muted-foreground" },
  { status: "planned", title: "Planned", Icon: Clock3, iconClass: "text-amber-600" },
  { status: "expired", title: "Overdue", Icon: AlertCircle, iconClass: "text-destructive" },
  { status: "done", title: "Done", Icon: CheckCircle2, iconClass: "text-sky-600" },
];

type Props = {
  newOpen: boolean;
  onNewOpenChange: (open: boolean) => void;
};

function truncate(text: string, n = 80): string {
  const t = (text || "").trim();
  if (t.length <= n) return t;
  return `${t.slice(0, n)}…`;
}

export function TasksPanel({ newOpen, onNewOpenChange }: Props) {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [dragId, setDragId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    const api = getApi();
    if (!api?.list_tasks) {
      setError("任务 API 不可用");
      setLoading(false);
      return;
    }
    try {
      const res = await api.list_tasks(true);
      setTasks(res.tasks || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const byStatus = useMemo(() => {
    const map: Record<string, TaskItem[]> = {
      pending: [],
      planned: [],
      expired: [],
      done: [],
    };
    for (const t of tasks) {
      const key = map[t.status] ? t.status : "pending";
      map[key].push(t);
    }
    return map;
  }, [tasks]);

  const onCreate = async () => {
    const api = getApi();
    if (!api || saving) return;
    const t = title.trim();
    if (!t) return;
    setSaving(true);
    try {
      const res = await api.add_task({
        title: t,
        content: content.trim(),
        status: "pending",
      });
      if (!res.ok) {
        setError(res.error || "创建失败");
        return;
      }
      setTitle("");
      setContent("");
      onNewOpenChange(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const moveTo = async (taskId: number, status: TaskStatus) => {
    const api = getApi();
    if (!api) return;
    const res = await api.update_task_status(taskId, status);
    if (!res.ok) {
      setError(res.error || "更新失败");
      return;
    }
    await refresh();
  };

  const onDelete = async (task: TaskItem) => {
    const ok = await confirmAction(`确定删除任务「${task.title}」？`, {
      title: "删除任务",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const api = getApi();
    if (!api) return;
    const res = await api.delete_task(task.id);
    if (!res.ok) {
      setError(res.error || "删除失败");
      return;
    }
    await refresh();
  };

  const onDrop = async (status: TaskStatus) => {
    if (dragId == null) return;
    const task = tasks.find((t) => t.id === dragId);
    setDragId(null);
    if (!task || task.status === status) return;
    await moveTo(dragId, status);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-page-canvas">
      <div className="flex shrink-0 items-center justify-end gap-2 px-4 py-2">
        <span className="mr-auto text-caption text-muted-foreground">{tasks.length} Tasks</span>
        <button
          type="button"
          onClick={() => onNewOpenChange(true)}
          className="h-8 rounded-md bg-primary px-2.5 text-label font-medium text-primary-foreground hover:opacity-90"
        >
          + New Task
        </button>
      </div>
      {error ? (
        <div className="border-b border-border px-4 py-2 text-body text-destructive">{error}</div>
      ) : null}
      {loading ? (
        <div className="flex flex-1 items-center justify-center text-body text-muted-foreground">
          加载任务…
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 gap-3 overflow-x-auto p-4">
          {COLUMNS.map((col) => {
            const items = byStatus[col.status] || [];
            const { Icon } = col;
            return (
              <section
                key={col.status}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => void onDrop(col.status)}
                className="flex w-[280px] shrink-0 flex-col rounded-xl bg-surface-hover/60 ring-1 ring-surface-border"
              >
                <header className="flex items-center gap-2 px-3 py-2.5">
                  <Icon className={cn("size-3.5", col.iconClass)} strokeWidth={1.75} />
                  <span className="text-body font-medium text-foreground">{col.title}</span>
                  <span className="text-caption text-muted-foreground">{items.length}</span>
                </header>
                <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 pb-3">
                  {items.map((task) => (
                    <article
                      key={task.id}
                      draggable
                      onDragStart={() => setDragId(task.id)}
                      onDragEnd={() => setDragId(null)}
                      className={cn(
                        "cursor-grab rounded-lg border border-surface-border bg-surface p-3",
                        "shadow-[var(--surface-shadow)] active:cursor-grabbing",
                        dragId === task.id && "opacity-60",
                      )}
                    >
                      <div className="text-micro text-muted-foreground">#{task.id}</div>
                      <h3 className="mt-0.5 text-body font-medium text-foreground">{task.title}</h3>
                      {task.content ? (
                        <p className="mt-1 text-caption leading-relaxed text-muted-foreground">
                          {truncate(task.content)}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-1">
                        {task.owner ? (
                          <span className="rounded-md bg-surface-selected px-1.5 py-0.5 text-micro text-muted-foreground">
                            {task.owner}
                          </span>
                        ) : null}
                        {task.due_at ? (
                          <span className="rounded-md bg-surface-selected px-1.5 py-0.5 text-micro text-muted-foreground">
                            {task.due_at}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {COLUMNS.filter((c) => c.status !== task.status).map((c) => (
                          <button
                            key={c.status}
                            type="button"
                            onClick={() => void moveTo(task.id, c.status)}
                            className="rounded-md px-1.5 py-0.5 text-micro text-muted-foreground hover:bg-surface-hover hover:text-foreground"
                          >
                            → {c.title}
                          </button>
                        ))}
                        <button
                          type="button"
                          onClick={() => void onDelete(task)}
                          className="rounded-md px-1.5 py-0.5 text-micro text-destructive hover:bg-surface-hover"
                        >
                          删除
                        </button>
                      </div>
                    </article>
                  ))}
                  {!items.length ? (
                    <div className="px-2 py-6 text-center text-caption text-muted-foreground">
                      暂无任务
                    </div>
                  ) : null}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {newOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border border-surface-border bg-surface p-5 shadow-[var(--menu-shadow)]">
            <h3 className="text-body font-semibold text-foreground">新建任务</h3>
            <input
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="标题"
              className="mt-3 h-9 w-full rounded-lg border border-surface-border bg-input px-3 text-body text-foreground outline-none focus:border-ring"
            />
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="描述（可选）"
              rows={4}
              className="mt-2 w-full rounded-lg border border-surface-border bg-input px-3 py-2 text-body text-foreground outline-none focus:border-ring"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => onNewOpenChange(false)}
                className="h-8 rounded-lg border border-surface-border px-3 text-label text-foreground hover:bg-surface-hover"
              >
                取消
              </button>
              <button
                type="button"
                disabled={saving || !title.trim()}
                onClick={() => void onCreate()}
                className="h-8 rounded-lg bg-primary px-3 text-label font-medium text-primary-foreground disabled:opacity-40"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
