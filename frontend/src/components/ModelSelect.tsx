import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { getApi } from "@/bridge/api";
import { useAppStore } from "@/stores/app-store";
import { cn } from "@/lib/cn";

export function ModelSelect() {
  const modelLabel = useAppStore((s) => s.modelLabel);
  const setModelLabel = useAppStore((s) => s.setModelLabel);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return models;
    return models.filter((m) => m.toLowerCase().includes(q));
  }, [models, query]);

  const loadModels = async () => {
    const api = getApi();
    if (!api) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.list_provider_models();
      const list = [...new Set(res.models || [])].sort((a, b) => a.localeCompare(b));
      const current = res.current_model || modelLabel;
      if (current && current !== "—" && !list.includes(current)) {
        list.unshift(current);
      }
      setModels(list);
      if (res.current_model) setModelLabel(res.current_model);
      if (res.error) setError(String(res.error));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setModels(modelLabel && modelLabel !== "—" ? [modelLabel] : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    void loadModels();
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const pick = async (model: string) => {
    const api = getApi();
    if (!api) return;
    const res = await api.set_model(model);
    if (!res.ok) {
      setError(res.error || "切换失败");
      return;
    }
    setModelLabel(res.model || model);
    setOpen(false);
  };

  const shortLabel =
    !modelLabel || modelLabel === "—"
      ? "选择模型"
      : modelLabel.includes("/")
        ? modelLabel.split("/").pop() || modelLabel
        : modelLabel;

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex max-w-[200px] items-center gap-1 rounded-lg px-2 py-1 text-micro transition",
          "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
          open && "bg-surface-hover text-foreground",
        )}
        title={modelLabel || "切换模型"}
      >
        <span className="truncate">{shortLabel}</span>
        <ChevronDown className="size-3 shrink-0 opacity-60" strokeWidth={2} />
      </button>
      {open ? (
        <div className="absolute right-0 bottom-full z-30 mb-2 w-72 overflow-hidden rounded-xl border border-surface-border bg-surface shadow-[var(--menu-shadow)]">
          <div className="flex items-center gap-2 border-b border-border p-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索模型…"
              className="min-w-0 flex-1 rounded-lg border border-surface-border bg-input px-2.5 py-1.5 text-caption text-foreground outline-none focus:border-ring"
            />
            <button
              type="button"
              onClick={() => void loadModels()}
              className="rounded-lg px-2 py-1.5 text-caption text-muted-foreground hover:bg-surface-hover hover:text-foreground"
            >
              {loading ? "…" : "刷新"}
            </button>
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            {filtered.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => void pick(m)}
                className={cn(
                  "block w-full truncate px-3 py-1.5 text-left text-caption",
                  m === modelLabel
                    ? "bg-surface-selected font-medium text-foreground"
                    : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
                )}
              >
                {m}
              </button>
            ))}
            {!filtered.length ? (
              <div className="px-3 py-3 text-center text-caption text-muted-foreground">
                {loading ? "加载中…" : "无可用模型"}
              </div>
            ) : null}
          </div>
          {error ? (
            <div className="border-t border-border px-3 py-1.5 text-micro text-destructive">
              {error}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
