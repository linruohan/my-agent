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
import {
  ArrowUp,
  FileText,
  Image as ImageIcon,
  Link2,
  Paperclip,
  Square,
  X,
} from "lucide-react";
import { getApi } from "@/bridge/api";
import type { AttachmentPayload, SlashCatalogItem } from "@/bridge/types";
import { useAppStore } from "@/stores/app-store";
import { ModelSelect } from "@/components/ModelSelect";
import { cn } from "@/lib/cn";

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

function autoResize(el: HTMLTextAreaElement | null) {
  if (!el) return;
  el.style.height = "0px";
  el.style.height = `${Math.min(Math.max(el.scrollHeight, 44), 200)}px`;
}

export function Composer() {
  const running = useAppStore((s) => s.running);
  const statusText = useAppStore((s) => s.statusText);
  const slashCatalog = useAppStore((s) => s.slashCatalog);
  const inputHistory = useAppStore((s) => s.inputHistory);
  const pushInputHistory = useAppStore((s) => s.pushInputHistory);
  const composerPrefill = useAppStore((s) => s.composerPrefill);
  const setComposerPrefill = useAppStore((s) => s.setComposerPrefill);
  const sessions = useAppStore((s) => s.sessions);

  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [slashIndex, setSlashIndex] = useState(0);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [historyDraft, setHistoryDraft] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const boxRef = useRef<HTMLTextAreaElement>(null);
  const attachRef = useRef<HTMLDivElement>(null);

  const activeSession = sessions.find((s) => s.active);
  const shortSessionId = activeSession?.id ? `${activeSession.id.slice(0, 8)}…` : "—";

  useEffect(() => {
    if (!composerPrefill) return;
    setText(composerPrefill);
    setComposerPrefill(null);
    requestAnimationFrame(() => {
      boxRef.current?.focus();
      autoResize(boxRef.current);
    });
  }, [composerPrefill, setComposerPrefill]);

  useEffect(() => {
    autoResize(boxRef.current);
  }, [text]);

  useEffect(() => {
    if (!attachMenuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!attachRef.current?.contains(e.target as Node)) setAttachMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [attachMenuOpen]);

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

  const readyLabel = (statusText || "就绪").replace(/^模型:[^|]*\|\s*/, "").trim();

  return (
    <form onSubmit={onSubmit} className="relative bg-page-canvas px-4 pt-2 pb-3">
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
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-2 text-left text-body",
                  idx === slashIndex ? "bg-surface-selected" : "hover:bg-surface-hover",
                )}
              >
                <span
                  className={cn(
                    "rounded-md px-1.5 py-0.5 font-mono text-micro",
                    item.kind === "skill"
                      ? "bg-brand/10 text-brand"
                      : "bg-surface-hover text-foreground",
                  )}
                >
                  {item.slash || `/${item.name}`}
                </span>
                <span className="truncate text-muted-foreground">{item.desc || ""}</span>
              </button>
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
          className={cn(
            "relative flex min-h-[72px] flex-col rounded-2xl border bg-surface pb-11",
            "shadow-[var(--surface-shadow)] transition-[border-color,box-shadow]",
            "focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/15",
            dragOver ? "border-brand ring-2 ring-brand/20" : "border-surface-border",
          )}
        >
          {attachments.length > 0 ? (
            <div className="flex flex-wrap gap-2 px-3 pt-3">
              {attachments.map((att, idx) => (
                <div
                  key={`${att.type}-${att.path || att.url || idx}`}
                  className="group/att relative flex max-w-[200px] items-center gap-2 rounded-xl border border-surface-border bg-surface-hover/60 py-1.5 pr-2 pl-1.5"
                >
                  {att.type === "image" && att.preview ? (
                    <img
                      src={att.preview}
                      alt={att.name || "image"}
                      className="size-9 rounded-lg object-cover"
                    />
                  ) : (
                    <span className="flex size-9 items-center justify-center rounded-lg bg-surface text-muted-foreground">
                      {att.type === "link" ? (
                        <Link2 className="size-3.5" strokeWidth={1.75} />
                      ) : (
                        <FileText className="size-3.5" strokeWidth={1.75} />
                      )}
                    </span>
                  )}
                  <span className="min-w-0 flex-1 truncate text-caption text-foreground">
                    {att.name || att.url || att.path || "附件"}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(idx)}
                    className="rounded-md p-0.5 text-faint-foreground opacity-70 transition hover:bg-surface hover:text-foreground group-hover/att:opacity-100"
                    aria-label="移除附件"
                  >
                    <X className="size-3.5" strokeWidth={1.75} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

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
            rows={1}
            placeholder="输入消息或 / 命令… 可粘贴图片"
            className="min-h-[44px] w-full resize-none bg-transparent px-3.5 pt-3 pb-2 text-body leading-relaxed text-foreground outline-none placeholder:text-faint-foreground"
          />

          {/* 底部工具条：左附件，右发送 */}
          <div className="absolute right-2 bottom-2 left-2 flex items-center justify-between">
            <div ref={attachRef} className="relative">
              <button
                type="button"
                onClick={() => setAttachMenuOpen((v) => !v)}
                className={cn(
                  "flex size-8 items-center justify-center rounded-lg text-muted-foreground transition",
                  "hover:bg-surface-hover hover:text-foreground",
                  attachMenuOpen && "bg-surface-hover text-foreground",
                )}
                title="添加附件"
                aria-label="添加附件"
              >
                <Paperclip className="size-4" strokeWidth={1.75} />
              </button>
              {attachMenuOpen ? (
                <div className="absolute bottom-full left-0 z-30 mb-1.5 min-w-[148px] overflow-hidden rounded-xl border border-surface-border bg-surface py-1 shadow-[var(--menu-shadow)]">
                  <button
                    type="button"
                    onClick={() => void pickImage()}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-label text-foreground hover:bg-surface-hover"
                  >
                    <ImageIcon className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                    图片
                  </button>
                  <button
                    type="button"
                    onClick={() => void pickFile()}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-label text-foreground hover:bg-surface-hover"
                  >
                    <FileText className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                    文件
                  </button>
                  <button
                    type="button"
                    onClick={promptLink}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-label text-foreground hover:bg-surface-hover"
                  >
                    <Link2 className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
                    链接
                  </button>
                </div>
              ) : null}
            </div>

            {running ? (
              <button
                type="button"
                onClick={() => void stop()}
                className="flex size-8 items-center justify-center rounded-full bg-destructive text-white shadow-sm transition hover:opacity-90"
                title="停止"
                aria-label="停止"
              >
                <Square className="size-3.5 fill-current" strokeWidth={0} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!canSend || sending}
                className={cn(
                  "flex size-8 items-center justify-center rounded-full transition",
                  canSend && !sending
                    ? "bg-primary text-primary-foreground shadow-sm hover:opacity-90"
                    : "bg-surface-selected text-faint-foreground",
                )}
                title="发送 (Enter)"
                aria-label="发送"
              >
                <ArrowUp className="size-4" strokeWidth={2.25} />
              </button>
            )}
          </div>

          {dragOver ? (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-brand/5 text-label font-medium text-brand">
              松开以添加附件
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-between gap-3 px-1">
          <div className="min-w-0 truncate text-micro text-muted-foreground">
            <span className={running ? "text-brand" : undefined}>{readyLabel || "就绪"}</span>
            <span className="mx-1.5 text-faint-foreground">·</span>
            <span className="text-faint-foreground" title={activeSession?.id}>
              {shortSessionId}
            </span>
          </div>
          <ModelSelect />
        </div>
      </div>
    </form>
  );
}
