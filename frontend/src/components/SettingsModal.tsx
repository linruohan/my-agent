import { useEffect, useState } from "react";
import { getApi } from "@/bridge/api";
import type { ProviderListItem, SettingsData } from "@/bridge/types";
import { useAppStore } from "@/stores/app-store";
import { ProviderEditor } from "@/components/ProviderEditor";
import { confirmAction } from "@/stores/confirm-store";

type TabId = "appearance" | "workspace" | "providers";

const TABS: { id: TabId; label: string }[] = [
  { id: "appearance", label: "外观" },
  { id: "workspace", label: "工作区" },
  { id: "providers", label: "模型" },
];

export function SettingsModal() {
  const open = useAppStore((s) => s.settingsOpen);
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen);
  const patchFromSettings = useAppStore((s) => s.patchFromSettings);
  const setModelLabel = useAppStore((s) => s.setModelLabel);

  const [tab, setTab] = useState<TabId>("appearance");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SettingsData | null>(null);
  const [themeId, setThemeId] = useState("default");
  const [appearance, setAppearance] = useState("dark");
  const [fontId, setFontId] = useState("system");
  const [owner, setOwner] = useState("");
  const [skillDirs, setSkillDirs] = useState("");
  const [providers, setProviders] = useState<ProviderListItem[]>([]);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<ProviderListItem | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setTab("appearance");
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const api = getApi();
        if (!api) throw new Error("API 不可用");
        const res = await api.get_settings_data();
        if (cancelled) return;
        setData(res);
        setThemeId(res.theme_id || "default");
        setAppearance(res.appearance || "dark");
        setFontId(res.font_id || "system");
        setOwner(res.task_owner_name || "");
        setSkillDirs(res.skill_dirs || "");
        setProviders(res.provider_list || []);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const onSave = async () => {
    const api = getApi();
    if (!api) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.save_settings({
        theme_id: themeId,
        appearance,
        font_id: fontId,
        skill_dirs: skillDirs,
        task_owner_name: owner,
      });
      if (!res.ok) {
        setError(res.error || "保存失败");
        return;
      }
      patchFromSettings({
        themeVariables: res.theme_variables,
        statusText: res.status_text,
        workspace: res.workspace,
        modelLabel: res.composer_meta?.current_model,
        themeId,
        appearance,
        fontId,
      });
      setSettingsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const onActivateProvider = async (providerId: string) => {
    const api = getApi();
    if (!api) return;
    const res = await api.activate_provider(providerId);
    if (!res.ok) {
      setError(res.error || "切换失败");
      return;
    }
    if (res.provider_list) setProviders(res.provider_list);
    if (res.composer_meta?.current_model) {
      setModelLabel(res.composer_meta.current_model);
    }
  };

  const onDeleteProvider = async (p: ProviderListItem) => {
    const ok = await confirmAction(`确定删除提供商「${p.display_name}」？`, {
      title: "删除提供商",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const api = getApi();
    if (!api) return;
    const res = await api.delete_provider(p.id);
    if (!res.ok) {
      setError(res.error || "删除失败");
      return;
    }
    if (res.provider_list) setProviders(res.provider_list);
    if (res.composer_meta?.current_model) {
      setModelLabel(res.composer_meta.current_model);
    }
  };

  const fieldClass =
    "w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-fg";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-[var(--radius-panel)] border border-border bg-panel shadow-lg">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-base font-semibold text-fg">设置</h2>
          <button
            type="button"
            onClick={() => setSettingsOpen(false)}
            className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-app hover:text-fg"
          >
            关闭
          </button>
        </div>

        <div className="flex gap-1 border-b border-border px-4 pt-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-t-lg px-3 py-2 text-sm transition ${
                tab === t.id
                  ? "bg-app font-medium text-fg"
                  : "text-muted-foreground hover:text-fg"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">加载中…</p>
          ) : (
            <>
              {tab === "appearance" ? (
                <section className="space-y-4">
                  <p className="text-xs text-muted-foreground">主题、明暗与界面字体</p>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-muted-foreground">主题</span>
                    <select
                      value={themeId}
                      onChange={(e) => setThemeId(e.target.value)}
                      className={fieldClass}
                    >
                      {(data?.theme_catalog || []).map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-muted-foreground">外观</span>
                    <select
                      value={appearance}
                      onChange={(e) => setAppearance(e.target.value)}
                      className={fieldClass}
                    >
                      <option value="light">浅色</option>
                      <option value="dark">深色</option>
                    </select>
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-muted-foreground">字体</span>
                    <select
                      value={fontId}
                      onChange={(e) => setFontId(e.target.value)}
                      className={fieldClass}
                    >
                      {(data?.font_catalog || [{ id: "system", name: "系统默认" }]).map(
                        (f) => (
                          <option key={f.id} value={f.id}>
                            {f.name}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                </section>
              ) : null}

              {tab === "workspace" ? (
                <section className="space-y-4">
                  <p className="text-xs text-muted-foreground">任务默认负责人与 Skill 扫描目录</p>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-muted-foreground">任务 Owner 名称</span>
                    <input
                      value={owner}
                      onChange={(e) => setOwner(e.target.value)}
                      className={fieldClass}
                      placeholder="例如：林若寒"
                    />
                    <span className="text-[11px] text-muted-foreground">
                      /tsk add 未指定 @owner 时使用
                    </span>
                  </label>
                  <label className="block space-y-1.5">
                    <span className="text-xs font-medium text-muted-foreground">Skill 目录（每行一个）</span>
                    <textarea
                      value={skillDirs}
                      onChange={(e) => setSkillDirs(e.target.value)}
                      rows={5}
                      className={`${fieldClass} font-mono text-xs`}
                    />
                  </label>
                </section>
              ) : null}

              {tab === "providers" ? (
                <section className="space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">切换、添加或编辑 LLM 提供商</p>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(null);
                        setEditorOpen(true);
                      }}
                      className="rounded px-2 py-1 text-xs text-accent hover:bg-app"
                    >
                      添加
                    </button>
                  </div>
                  <div className="max-h-64 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
                    {providers.map((p) => (
                      <div
                        key={p.id}
                        className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                          p.active ? "bg-app" : ""
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => void onActivateProvider(p.id)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <div
                            className={`truncate ${
                              p.active ? "font-medium text-fg" : "text-muted-foreground"
                            }`}
                          >
                            {p.display_name}
                            {p.active ? (
                              <span className="ml-2 text-[10px] text-accent">使用中</span>
                            ) : null}
                          </div>
                          <div className="truncate font-mono text-[11px] text-muted-foreground">
                            {p.model}
                          </div>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(p);
                            setEditorOpen(true);
                          }}
                          className="rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-panel hover:text-fg"
                        >
                          编辑
                        </button>
                        {p.deletable ? (
                          <button
                            type="button"
                            onClick={() => void onDeleteProvider(p)}
                            className="rounded px-1.5 py-0.5 text-xs text-danger hover:bg-panel"
                          >
                            删除
                          </button>
                        ) : null}
                      </div>
                    ))}
                    {!providers.length ? (
                      <div className="px-2 py-2 text-xs text-muted-foreground">暂无提供商</div>
                    ) : null}
                  </div>
                </section>
              ) : null}
            </>
          )}
          {error ? <p className="text-sm text-danger">{error}</p> : null}
        </div>

        <div className="flex justify-end gap-2 border-t border-border px-5 py-4">
          <button
            type="button"
            onClick={() => setSettingsOpen(false)}
            className="rounded-lg border border-border px-3 py-2 text-sm text-fg"
          >
            取消
          </button>
          <button
            type="button"
            disabled={loading || saving}
            onClick={() => void onSave()}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-fg disabled:opacity-40"
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>

      <ProviderEditor
        open={editorOpen}
        provider={editing}
        onClose={() => setEditorOpen(false)}
        onSaved={(list, meta) => {
          setProviders(list);
          if (meta?.model) setModelLabel(meta.model);
        }}
      />
    </div>
  );
}
