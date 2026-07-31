import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { getApi } from "@/bridge/api";
import type { AttachmentPayload, SlashCatalogItem } from "@/bridge/types";
import { useAppStore } from "@/stores/app-store";
import { ModelSelect } from "@/components/ModelSelect";

type LocalAttachment = AttachmentPayload & { preview?: string };

function filterSlash(catalog: SlashCatalogItem[], text: string): SlashCatalogItem[] {
  if (!text.startsWith("/")) return [];
  const rest = text.slice(1).toLowerCase();
  return catalog.filter((item) => {
    const name = (item.name || "").toLowerCase();
    const desc = (item.desc || "").toLowerCase();
    const slash = (item.slash || `/${item.name}`).toLowerCase();
    if (!rest) return true;
    return name.includes(rest) || desc.includes(rest) || slash.includes(`/${rest}`);
  });
}

function basename(path: string): string {
  return path.split(/[/\\]/).pop() || path;
}

export function Composer() {
  const running = useAppStore((s) => s.running);
  const statusText = useAppStore((s) => s.statusText);
  const slashCatalog = useAppStore((s) => s.slashCatalog);
  const inputHistory = useAppStore((s) => s.inputHistory);
  const pushInputHistory = useAppStore((s) => s.pushInputHistory);
  const composerPrefill = useAppStore((s) => s.composerPrefill);
  const setComposerPrefill = useAppStore((s) => s.setComposerPrefill);

  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [slashIndex, setSlashIndex] = useState(0);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [historyDraft, setHistoryDraft] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const boxRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!composerPrefill) return;
    setText(composerPrefill);
    setComposerPrefill(null);
    requestAnimationFrame(() => boxRef.current?.focus());
  }, [composerPrefill, setComposerPrefill]);

  const slashItems = useMemo(() => filterSlash(slashCatalog, text), [slashCatalog, text]);
  const slashOpen = slashItems.length > 0;
  const canSend = Boolean(text.trim() || attachments.length);

  const addAttachment = useCallback((att: LocalAttachment) => {
    setAttachments((prev) => [...prev, att]);
  }, []);

  const removeAttachment = useCallback((idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const applySlash = useCallback((item: SlashCatalogItem) => {
    setText(item.slash || `/${item.name}`);
    setSlashIndex(0);
    boxRef.current?.focus();
  }, []);

  const pickImage = useCallback(async () => {
    setAttachMenuOpen(false);
    const api = getApi();
    if (!api) return;
    const res = await api.pick_input_image();
    for (const path of res.paths || []) {
      let preview: string | undefined;
      try {
        const img = await api.read_image_data_url(path);
        if (img.ok) preview = img.data_url;
      } catch {
        preview = undefined;
      }
      addAttachment({ type: "image", path, name: basename(path), preview });
    }
  }, [addAttachment]);

  const pickFile = useCallback(async () => {
    setAttachMenuOpen(false);
    const api = getApi();
    if (!api) return;
    const res = await api.pick_input_file();
    for (const path of res.paths || []) {
      addAttachment({ type: "file", path, name: basename(path) });
    }
  }, [addAttachment]);

  const promptLink = useCallback(() => {
    setAttachMenuOpen(false);
    const url = window.prompt("输入链接 URL（http/https）");
    if (!url?.trim()) return;
    addAttachment({ type: "link", url: url.trim() });
  }, [addAttachment]);

  const submit = useCallback(async () => {
    const value = text.trim();
    if ((!value && !attachments.length) || running || sending) return;
    const api = getApi();
    if (!api) return;
    setSending(true);
    try {
      const payload = {
        text: value,
        attachments: attachments.map(({ type, path, url, name }) => ({
          type,
          path,
          url,
          name,
        })),
      };
      const ok = await api.send_message(payload);
      if (ok !== false) {
        if (value) pushInputHistory(value);
        setText("");
        setAttachments([]);
        setHistoryIndex(-1);
        setHistoryDraft("");
        setAttachMenuOpen(false);
      }
    } finally {
      setSending(false);
    }
  }, [text, attachments, running, sending, pushInputHistory]);

  const stop = useCallback(async () => {
    const api = getApi();
    if (!api) return;
    await api.stop_agent();
  }, []);

  const onPaste = async (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    const api = getApi();
    if (!items || !api) return;
    for (const item of items) {
      if (!item.type.startsWith("image/")) continue;
      e.preventDefault();
      const blob = item.getAsFile();
      if (!blob) continue;
      const reader = new FileReader();
      reader.onload = async () => {
        const dataUrl = String(reader.result);
        const saved = await api.save_pasted_image(dataUrl);
        if (saved.ok && saved.path) {
          addAttachment({
            type: "image",
            path: saved.path,
            name: blob.name || "clipboard.png",
            preview: dataUrl,
          });
        }
      };
      reader.readAsDataURL(blob);
      return;
    }
  };

  const onDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const api = getApi();
    if (!api) return;
    const files = e.dataTransfer?.files;
    if (files?.length) {
      for (const file of Array.from(files)) {
        const path = (file as File & { path?: string }).path;
        if (path) {
          if (file.type.startsWith("image/")) {
            let preview: string | undefined;
            try {
              const img = await api.read_image_data_url(path);
              if (img.ok) preview = img.data_url;
            } catch {
              preview = undefined;
            }
            addAttachment({ type: "image", path, name: file.name, preview });
          } else {
            addAttachment({ type: "file", path, name: file.name });
          }
          continue;
        }
        if (file.type.startsWith("image/")) {
          const reader = new FileReader();
          reader.onload = async () => {
            const dataUrl = String(reader.result);
            const saved = await api.save_pasted_image(dataUrl);
            if (saved.ok && saved.path) {
              addAttachment({
                type: "image",
                path: saved.path,
                name: file.name,
                preview: dataUrl,
              });
            }
          };
          reader.readAsDataURL(file);
        }
      }
      return;
    }
    const plain = e.dataTransfer?.getData("text/plain")?.trim();
    if (plain) {
      setText((prev) => (prev ? `${prev}\n${plain}` : plain));
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (slashOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSlashIndex((i) => (i + 1) % slashItems.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSlashIndex((i) => (i - 1 + slashItems.length) % slashItems.length);
        return;
      }
      if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
        e.preventDefault();
        const item = slashItems[slashIndex] || slashItems[0];
        if (item) applySlash(item);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setText("");
        return;
      }
    }

    if (e.key === "ArrowUp" && !e.shiftKey && inputHistory.length) {
      const box = boxRef.current;
      if (box && box.value.slice(0, box.selectionStart).indexOf("\n") === -1) {
        e.preventDefault();
        setHistoryIndex((prev) => {
          if (prev === -1) setHistoryDraft(text);
          const next = Math.min(prev + 1, inputHistory.length - 1);
          setText(inputHistory[next] || "");
          return next;
        });
        return;
      }
    }
    if (e.key === "ArrowDown" && historyIndex >= 0) {
      const box = boxRef.current;
      if (box && box.value.slice(box.selectionStart).indexOf("\n") === -1) {
        e.preventDefault();
        setHistoryIndex((prev) => {
          if (prev <= 0) {
            setText(historyDraft);
            return -1;
          }
          const next = prev - 1;
          setText(inputHistory[next] || "");
          return next;
        });
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void submit();
  };

  return (
    <form onSubmit={onSubmit} className="relative border-t border-border bg-page-canvas px-4 py-3">
      <div className="chat-column relative flex flex-col gap-2">
        {slashOpen ? (
          <div className="absolute right-0 bottom-full left-0 z-20 mb-2 max-h-56 overflow-y-auto rounded-xl border border-surface-border bg-surface shadow-[var(--menu-shadow)]">
            {slashItems.map((item, idx) => (
              <button
                key={`${item.kind}-${item.name}`}
                type="button"
                onMouseDown={(ev) => {
                  ev.preventDefault();
                  applySlash(item);
                }}
                className={`flex w-full items-center gap-3 px-3 py-2 text-left text-body ${
                  idx === slashIndex ? "bg-surface-selected" : "hover:bg-surface-hover"
                }`}
              >
                <span
                  className={`rounded-md px-1.5 py-0.5 font-mono text-micro ${
                    item.kind === "skill"
                      ? "bg-brand/10 text-brand"
                      : "bg-surface-hover text-foreground"
                  }`}
                >
                  {item.slash || `/${item.name}`}
                </span>
                <span className="truncate text-muted-foreground">{item.desc || ""}</span>
              </button>
            ))}
          </div>
        ) : null}

        {attachments.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {attachments.map((att, idx) => (
              <div
                key={`${att.type}-${att.path || att.url || idx}`}
                className="flex max-w-[220px] items-center gap-2 rounded-lg border border-surface-border bg-surface px-2 py-1.5 text-caption text-foreground"
              >
                {att.type === "image" && att.preview ? (
                  <img
                    src={att.preview}
                    alt={att.name || "image"}
                    className="size-8 rounded object-cover"
                  />
                ) : (
                  <span className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-micro uppercase text-muted-foreground">
                    {att.type}
                  </span>
                )}
                <span className="min-w-0 flex-1 truncate">
                  {att.name || att.url || att.path || "附件"}
                </span>
                <button
                  type="button"
                  onClick={() => removeAttachment(idx)}
                  className="text-faint-foreground hover:text-foreground"
                  aria-label="移除附件"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        ) : null}

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => void onDrop(e)}
          className={`relative flex items-end gap-2 rounded-xl border bg-surface px-2 py-2 shadow-[var(--surface-shadow)] ${
            dragOver ? "border-brand ring-1 ring-brand/20" : "border-surface-border"
          }`}
        >
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setAttachMenuOpen((v) => !v)}
              className="rounded-lg px-2 py-2 text-body text-muted-foreground hover:bg-surface-hover hover:text-foreground"
              title="添加附件"
            >
              +
            </button>
            {attachMenuOpen ? (
              <div className="absolute bottom-full left-0 z-30 mb-1 min-w-[140px] overflow-hidden rounded-lg border border-surface-border bg-surface shadow-[var(--menu-shadow)]">
                <button
                  type="button"
                  onClick={() => void pickImage()}
                  className="block w-full px-3 py-2 text-left text-body text-foreground hover:bg-surface-hover"
                >
                  图片
                </button>
                <button
                  type="button"
                  onClick={() => void pickFile()}
                  className="block w-full px-3 py-2 text-left text-body text-foreground hover:bg-surface-hover"
                >
                  文件
                </button>
                <button
                  type="button"
                  onClick={promptLink}
                  className="block w-full px-3 py-2 text-left text-body text-foreground hover:bg-surface-hover"
                >
                  链接
                </button>
              </div>
            ) : null}
          </div>

          <textarea
            ref={boxRef}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setSlashIndex(0);
              setHistoryIndex(-1);
            }}
            onKeyDown={onKeyDown}
            onPaste={(e) => void onPaste(e)}
            rows={2}
            placeholder="输入消息或 / 命令… 可粘贴图片"
            className="min-h-[52px] flex-1 resize-none bg-transparent text-body text-foreground outline-none placeholder:text-faint-foreground"
          />
          {running ? (
            <button
              type="button"
              onClick={() => void stop()}
              className="shrink-0 rounded-lg bg-destructive px-3 py-2 text-label font-medium text-white"
            >
              停止
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend || sending}
              className="shrink-0 rounded-lg bg-primary px-3 py-2 text-label font-medium text-primary-foreground disabled:opacity-40"
            >
              发送
            </button>
          )}
        </div>
        <div className="flex items-center justify-between px-1 text-micro text-muted-foreground">
          <span>{statusText || "就绪"}</span>
          <ModelSelect />
        </div>
      </div>
    </form>
  );
}
