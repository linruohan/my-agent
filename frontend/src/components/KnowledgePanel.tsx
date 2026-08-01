import { useEffect, useState } from "react";
import { getApi } from "@/bridge/api";

export function KnowledgePanel() {
  const [stats, setStats] = useState("加载中…");
  const [log, setLog] = useState("");
  const [busy, setBusy] = useState(false);

  const refreshStats = async () => {
    const api = getApi();
    if (!api) return;
    try {
      const res = await api.get_knowledge_stats();
      setStats(res.text || "");
    } catch (err) {
      setStats(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void refreshStats();
  }, []);

  const doImport = async (kind: "files" | "folder") => {
    const api = getApi();
    if (!api || busy) return;
    setBusy(true);
    setLog("");
    try {
      const res = await api.import_knowledge(kind);
      if (res.log) setLog(res.log);
      if (res.text) setStats(res.text);
      else await refreshStats();
    } catch (err) {
      setLog(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-app">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
        <section className="rounded-[var(--radius-panel)] border border-border bg-panel p-4">
          <h3 className="text-sm font-semibold text-fg">索引状态</h3>
          <pre className="mt-3 whitespace-pre-wrap font-mono text-xs leading-relaxed text-muted-foreground">
            {stats}
          </pre>
          <button
            type="button"
            onClick={() => void refreshStats()}
            className="mt-3 rounded-lg border border-border px-3 py-1.5 text-sm text-fg hover:bg-app"
          >
            刷新
          </button>
        </section>

        <section className="rounded-[var(--radius-panel)] border border-border bg-panel p-4">
          <h3 className="text-sm font-semibold text-fg">导入文档</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            支持 txt / md / pdf / docx。导入在后台进行，完成后会在会话中提示。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void doImport("files")}
              className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-fg disabled:opacity-40"
            >
              选择文件
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void doImport("folder")}
              className="rounded-lg border border-border px-3 py-2 text-sm text-fg hover:bg-app disabled:opacity-40"
            >
              选择文件夹
            </button>
          </div>
          {log ? (
            <pre className="mt-3 max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-muted-foreground">
              {log}
            </pre>
          ) : null}
        </section>
      </div>
    </div>
  );
}
