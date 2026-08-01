import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  BookOpen,
  LayoutDashboard,
  MessageSquare,
  Search,
  Sparkles,
} from "lucide-react";
import { getApi } from "@/bridge/api";
import type { SlashCatalogItem, TaskItem } from "@/bridge/types";
import { useAppStore } from "@/stores/app-store";
import { applySessionApiResult } from "@/lib/session-api";
import { cn } from "@/lib/cn";

type HitKind = "session" | "task" | "skill" | "knowledge";

type SearchHit = {
  kind: HitKind;
  id: string;
  title: string;
  subtitle?: string;
};

const KIND_META: Record<
  HitKind,
  { label: string; Icon: typeof Search }
> = {
  session: { label: "会话", Icon: MessageSquare },
  task: { label: "任务", Icon: LayoutDashboard },
  skill: { label: "Skill", Icon: Sparkles },
  knowledge: { label: "Knowledge", Icon: BookOpen },
};

function matchText(hay: string, q: string): boolean {
  return hay.toLowerCase().includes(q);
}

type Props = {
  collapsed?: boolean;
  className?: string;
};

export function GlobalSearch({ collapsed, className }: Props) {
  const sessions = useAppStore((s) => s.sessions);
  const slashCatalog = useAppStore((s) => s.slashCatalog);
  const setActiveView = useAppStore((s) => s.setActiveView);
  const setSessions = useAppStore((s) => s.setSessions);
  const setComposerPrefill = useAppStore((s) => s.setComposerPrefill);

  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [knowledgeLines, setKnowledgeLines] = useState<string[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQuery(query), 150);
    return () => window.clearTimeout(t);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const api = getApi();
    void (async () => {
      try {
        if (api?.list_tasks) {
          const res = await api.list_tasks(true);
          if (!cancelled && res?.tasks) setTasks(res.tasks);
        }
      } catch {
        /* ignore */
      }
      try {
        if (api?.get_knowledge_stats) {
          const res = await api.get_knowledge_stats();
          if (!cancelled && res?.text) {
            setKnowledgeLines(
              res.text
                .split(/\r?\n/)
                .map((l) => l.trim())
                .filter(Boolean),
            );
          }
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const hits = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    if (!q) return [] as SearchHit[];
    const out: SearchHit[] = [];

    for (const s of sessions) {
      if (matchText(s.title || "未命名", q) || matchText(s.id, q)) {
        out.push({
          kind: "session",
          id: s.id,
          title: s.title || "未命名",
          subtitle: s.active ? "当前会话" : undefined,
        });
      }
    }

    for (const t of tasks) {
      const blob = `${t.title} ${t.content || ""} ${(t.tags || []).join(" ")}`;
      if (matchText(blob, q) || matchText(String(t.id), q)) {
        out.push({
          kind: "task",
          id: String(t.id),
          title: t.title,
          subtitle: `${t.status}${t.content ? ` · ${t.content.slice(0, 40)}` : ""}`,
        });
      }
    }

    for (const item of slashCatalog) {
      if (item.kind !== "skill") continue;
      const blob = `${item.name} ${item.desc || ""} ${item.slash || ""}`;
      if (matchText(blob, q)) {
        out.push({
          kind: "skill",
          id: item.name,
          title: item.slash || `/${item.name}`,
          subtitle: item.desc || undefined,
        });
      }
    }

    for (const line of knowledgeLines) {
      if (matchText(line, q)) {
        out.push({
          kind: "knowledge",
          id: line,
          title: line.length > 72 ? `${line.slice(0, 72)}…` : line,
          subtitle: "知识库",
        });
      }
    }

    return out.slice(0, 40);
  }, [debouncedQuery, sessions, tasks, slashCatalog, knowledgeLines]);

  useEffect(() => {
    setActiveIndex(0);
  }, [debouncedQuery, hits.length]);

  const grouped = useMemo(() => {
    const order: HitKind[] = ["session", "task", "skill", "knowledge"];
    return order
      .map((kind) => ({ kind, items: hits.filter((h) => h.kind === kind) }))
      .filter((g) => g.items.length > 0);
  }, [hits]);

  const flatHits = useMemo(() => grouped.flatMap((g) => g.items), [grouped]);

  const applyHit = async (hit: SearchHit) => {
    setOpen(false);
    setQuery("");
    const api = getApi();

    if (hit.kind === "session") {
      setActiveView("chat");
      if (!api || !hit.id) return;
      const res = await api.switch_session(hit.id);
      applySessionApiResult(res, setSessions);
      return;
    }

    if (hit.kind === "task") {
      setActiveView("tasks");
      return;
    }

    if (hit.kind === "skill") {
      const item = slashCatalog.find(
        (s: SlashCatalogItem) => s.kind === "skill" && s.name === hit.id,
      );
      setComposerPrefill(item?.slash || `/${hit.id}`);
      setActiveView("chat");
      return;
    }

    if (hit.kind === "knowledge") {
      setActiveView("knowledge");
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (!flatHits.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % flatHits.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + flatHits.length) % flatHits.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = flatHits[activeIndex];
      if (hit) void applyHit(hit);
    }
  };

  if (collapsed) {
    return (
      <div ref={rootRef} className={cn("relative", className)}>
        <button
          type="button"
          title="搜索"
          onClick={() => {
            setOpen(true);
            requestAnimationFrame(() => inputRef.current?.focus());
          }}
          className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <Search className="size-4" strokeWidth={1.75} />
        </button>
        {open ? (
          <div className="absolute top-0 left-10 z-50 w-72 rounded-xl border border-surface-border bg-surface p-2 shadow-[var(--menu-shadow)]">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-faint-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="搜索会话、任务、Skill…"
                className="h-8 w-full rounded-lg border border-surface-border bg-input pr-2 pl-8 text-label outline-none focus:border-ring"
                autoFocus
              />
            </div>
            <Results
              query={query}
              grouped={grouped}
              flatHits={flatHits}
              activeIndex={activeIndex}
              onPick={(h) => void applyHit(h)}
            />
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div ref={rootRef} className={cn("relative min-w-0 flex-1", className)}>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-faint-foreground" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="搜索会话、任务、Skill、知识…"
          className="h-8 w-full rounded-lg border-0 bg-sidebar-accent/60 pr-2 pl-8 text-caption text-sidebar-foreground outline-none placeholder:text-faint-foreground focus:bg-sidebar-accent"
        />
      </div>
      {open && query.trim() ? (
        <div className="absolute top-full right-0 left-0 z-50 mt-1 max-h-[min(420px,55vh)] overflow-y-auto rounded-xl border border-surface-border bg-surface py-1 shadow-[var(--menu-shadow)]">
          <Results
            query={query}
            grouped={grouped}
            flatHits={flatHits}
            activeIndex={activeIndex}
            onPick={(h) => void applyHit(h)}
          />
        </div>
      ) : null}
    </div>
  );
}

function Results({
  query,
  grouped,
  flatHits,
  activeIndex,
  onPick,
}: {
  query: string;
  grouped: { kind: HitKind; items: SearchHit[] }[];
  flatHits: SearchHit[];
  activeIndex: number;
  onPick: (hit: SearchHit) => void;
}) {
  if (!query.trim()) {
    return (
      <div className="px-3 py-4 text-center text-caption text-muted-foreground">
        输入关键词搜索
      </div>
    );
  }
  if (!flatHits.length) {
    return (
      <div className="px-3 py-4 text-center text-caption text-muted-foreground">
        无匹配结果
      </div>
    );
  }

  let offset = 0;
  return (
    <div className="py-1">
      {grouped.map(({ kind, items }) => {
        const meta = KIND_META[kind];
        const Icon = meta.Icon;
        const start = offset;
        offset += items.length;
        return (
          <div key={kind} className="mb-1">
            <div className="px-3 py-1 text-micro font-medium tracking-wide text-faint-foreground uppercase">
              {meta.label}
            </div>
            {items.map((hit, i) => {
              const idx = start + i;
              const active = idx === activeIndex;
              return (
                <button
                  key={`${hit.kind}-${hit.id}-${i}`}
                  type="button"
                  onClick={() => onPick(hit)}
                  className={cn(
                    "flex w-full items-start gap-2 px-3 py-1.5 text-left transition",
                    active ? "bg-surface-selected" : "hover:bg-surface-hover",
                  )}
                >
                  <Icon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" strokeWidth={1.75} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-label text-foreground">{hit.title}</span>
                    {hit.subtitle ? (
                      <span className="block truncate text-micro text-muted-foreground">
                        {hit.subtitle}
                      </span>
                    ) : null}
                  </span>
                </button>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
