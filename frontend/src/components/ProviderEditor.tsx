import { useEffect, useState } from "react";
import type { ProviderListItem } from "@/bridge/types";
import { getApi } from "@/bridge/api";

type Props = {
  provider: ProviderListItem | null;
  open: boolean;
  onClose: () => void;
  onSaved: (list: ProviderListItem[], meta?: { model?: string; status?: string }) => void;
};

const TYPES = [
  { value: "openai_compatible", label: "OpenAI Compatible" },
  { value: "openai", label: "OpenAI" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "ollama", label: "Ollama" },
];

export function ProviderEditor({ provider, open, onClose, onSaved }: Props) {
  const isNew = !provider;
  const [displayName, setDisplayName] = useState("");
  const [type, setType] = useState("openai_compatible");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [hint, setHint] = useState("");
  const [hintOk, setHintOk] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDisplayName(provider?.display_name || "");
    setType(provider?.type || "openai_compatible");
    setModel(provider?.model || "");
    setBaseUrl(provider?.base_url || "");
    setApiKey("");
    setTemperature(provider?.temperature ?? 0.7);
    if (provider?.has_api_key) {
      setHint("已配置 API Key（留空保留，输入新值覆盖）");
      setHintOk(true);
    } else {
      setHint(isNew ? "请填写 API Key" : "尚未配置 API Key");
      setHintOk(false);
    }
  }, [open, provider, isNew]);

  if (!open) return null;

  const onSave = async () => {
    const api = getApi();
    if (!api) return;
    setSaving(true);
    setHint("");
    try {
      const res = await api.save_provider({
        id: provider?.id || "",
        display_name: displayName.trim(),
        type,
        model: model.trim(),
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
        temperature,
      });
      if (!res.ok) {
        setHint(res.error || "保存失败");
        setHintOk(false);
        return;
      }
      onSaved(res.provider_list || [], {
        model: res.composer_meta?.current_model,
        status: res.status_text,
      });
      onClose();
    } catch (err) {
      setHint(err instanceof Error ? err.message : String(err));
      setHintOk(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-[var(--radius-panel)] border border-border bg-panel shadow-lg">
        <div className="border-b border-border px-5 py-4">
          <h3 className="text-sm font-semibold text-fg">
            {isNew ? "添加提供商" : "编辑提供商"}
          </h3>
        </div>
        <div className="space-y-3 px-5 py-4">
          <label className="block space-y-1">
            <span className="text-xs text-muted">显示名称</span>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-fg"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-muted">类型</span>
            <select
              value={type}
              disabled={!!provider?.is_builtin}
              onChange={(e) => setType(e.target.value)}
              className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-fg disabled:opacity-60"
            >
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-muted">模型</span>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-fg"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-muted">Base URL</span>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.example.com/v1"
              className="w-full rounded-lg border border-border bg-input px-3 py-2 font-mono text-xs text-fg"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-muted">API Key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-fg"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs text-muted">Temperature: {temperature}</span>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
              className="w-full"
            />
          </label>
          {hint ? (
            <p className={`text-xs ${hintOk ? "text-muted" : "text-danger"}`}>{hint}</p>
          ) : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-3 py-2 text-sm text-fg"
          >
            取消
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => void onSave()}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-fg disabled:opacity-40"
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
