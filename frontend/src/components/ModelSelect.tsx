import { useEffect, useMemo, useRef, useState } from "react";
import { getApi } from "@/bridge/api";
import { useAppStore } from "@/stores/app-store";

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
      const list = [...new Set(res.models || [])].sort((a, b) =>
        a.localeCompare(b),
      );
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

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="max-w-[180px] truncate rounded px-1.5 py-0.5 text-[11px] text-muted hover:bg-app hover:text-fg"
        title="切换模型"
      >
        {modelLabel || "选择模型"}
      </button>
      {open ? (
        <div className="absolute right-0 bottom-full z-30 mb-2 w-64 overflow-hidden rounded-lg border border-border bg-panel shadow-lg">
          <div className="flex items-center gap-2 border-b border-border p-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索模型…"
              className="min-w-0 flex-1 rounded border border-border bg-input px-2 py-1 text-xs text-fg outline-none"
            />
            <button
              type="button"
              onClick={() => void loadModels()}
              className="rounded px-2 py-1 text-xs text-muted hover:bg-app hover:text-fg"
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
                className={`block w-full truncate px-3 py-1.5 text-left text-xs ${
                  m === modelLabel
                    ? "bg-app font-medium text-fg"
                    : "text-muted hover:bg-app hover:text-fg"
                }`}
              >
                {m}
              </button>
            ))}
            {!filtered.length ? (
              <div className="px-3 py-2 text-xs text-muted">
                {loading ? "加载中…" : "无可用模型"}
              </div>
            ) : null}
          </div>
          {error ? (
            <div className="border-t border-border px-3 py-1.5 text-[11px] text-danger">
              {error}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
