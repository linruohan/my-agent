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
  Plus,
  Square,
  X,
} from "lucide-react";
import { getApi } from "@/bridge/api";
import type { AttachmentPayload, SlashCatalogItem } from "@/bridge/types";
import { useAppStore } from "@/stores/app-store";
import { ModelSelect } from "@/components/ModelSelect";
import { cn } from "@/lib/cn";

type LocalAttachment = AttachmentPayload & { preview?: string };

/**
 * 过滤斜杠命令匹配
 *
 * @param catalog - 斜杠命令目录
 * @param text - 当前输入框文本
 * @returns 匹配到的斜杠命令列表
 */
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

/**
 * 从完整路径中提取文件名
 *
 * @param path - 文件完整路径
 * @returns 文件名（含扩展名）
 */
function basename(path: string): string {
  return path.split(/[/\\]/).pop() || path;
}

/**
 * 输入框自动调整高度
 *
 * @param el - textarea DOM 元素
 */
function autoResize(el: HTMLTextAreaElement | null, compact: boolean) {
  if (!el) return;
  if (compact) {
    el.style.height = "28px";
    return;
  }
  el.style.height = "0px";
  el.style.height = `${Math.min(Math.max(el.scrollHeight, 44), 200)}px`;
}

/**
 * Composer - 聊天输入组件
 *
 * 功能：
 * - 多行自适应高度文本输入
 * - 斜杠命令搜索与自动补全
 * - 附件上传：图片/文件/链接（粘贴 + 拖拽 + 按钮菜单）
 * - 发送/停止按钮切换
 * - 模型选择下拉
 * - 输入历史上/下方向键回溯
 * - 底部浮动胶囊输入条（附件 + 文本 + 模型 + 发送）
 */
export function Composer() {
  const running = useAppStore((s) => s.running);
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
  const attachRef = useRef<HTMLDivElement>(null);

  const slashItems = useMemo(() => filterSlash(slashCatalog, text), [slashCatalog, text]);
  const slashOpen = slashItems.length > 0;
  const canSend = Boolean(text.trim() || attachments.length);
  /** 有内容/附件/斜杠菜单时展开为多行卡片，否则为单行胶囊 */
  const expanded = Boolean(text.length > 0 || attachments.length > 0 || slashOpen || dragOver);

  /* 外部预填文本（例如快捷指令跳转） */
  useEffect(() => {
    if (!composerPrefill) return;
    setText(composerPrefill);
    setComposerPrefill(null);
    requestAnimationFrame(() => {
      boxRef.current?.focus();
      autoResize(boxRef.current, false);
    });
  }, [composerPrefill, setComposerPrefill]);

  /* 文本变化时调整输入框高度 */
  useEffect(() => {
    autoResize(boxRef.current, !expanded);
  }, [text, expanded]);

  /* 点击外部关闭附件菜单 */
  useEffect(() => {
    if (!attachMenuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!attachRef.current?.contains(e.target as Node)) setAttachMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [attachMenuOpen]);

  /**
   * 添加单个附件到列表
   */
  const addAttachment = useCallback((att: LocalAttachment) => {
    setAttachments((prev) => [...prev, att]);
  }, []);

  /**
   * 按索引移除附件
   */
  const removeAttachment = useCallback((idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  /**
   * 选择指定斜杠命令并填充到输入框
   */
  const applySlash = useCallback((item: SlashCatalogItem) => {
    setText(item.slash || `/${item.name}`);
    setSlashIndex(0);
    boxRef.current?.focus();
  }, []);

  /**
   * 选择本地图片附件
   */
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

  /**
   * 选择本地文件附件
   */
  const pickFile = useCallback(async () => {
    setAttachMenuOpen(false);
    const api = getApi();
    if (!api) return;
    const res = await api.pick_input_file();
    for (const path of res.paths || []) {
      addAttachment({ type: "file", path, name: basename(path) });
    }
  }, [addAttachment]);

  /**
   * 弹窗输入 URL 并作为链接附件
   */
  const promptLink = useCallback(() => {
    setAttachMenuOpen(false);
    const url = window.prompt("输入链接 URL（http/https）");
    if (!url?.trim()) return;
    addAttachment({ type: "link", url: url.trim() });
  }, [addAttachment]);

  /**
   * 提交消息（发送到后端）
   */
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

  /**
   * 停止当前正在生成的响应
   */
  const stop = useCallback(async () => {
    const api = getApi();
    if (!api) return;
    await api.stop_agent();
  }, []);

  /**
   * 粘贴事件：若剪贴板是图片则自动保存为附件
   */
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

  /**
   * 拖放事件：拖入文件/图片/文本
   */
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

  /**
   * 键盘事件：斜杠补全 / 历史回溯 / Enter 发送
   */
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

  const attachMenu = attachMenuOpen ? (
    <div className="absolute bottom-full left-0 z-30 mb-2 min-w-[148px] overflow-hidden rounded-xl border border-surface-border bg-surface-raised py-1 shadow-[var(--menu-shadow)]">
      {[
        { icon: ImageIcon, label: "图片", onClick: () => void pickImage() },
        { icon: FileText, label: "文件", onClick: () => void pickFile() },
        { icon: Link2, label: "链接", onClick: promptLink },
      ].map((it) => (
        <button
          key={it.label}
          type="button"
          onClick={it.onClick}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-body text-foreground hover:bg-surface-hover"
        >
          <it.icon className="size-3.5 text-muted-foreground" strokeWidth={1.75} />
          {it.label}
        </button>
      ))}
    </div>
  ) : null;

  const sendBtn = running ? (
    <button
      type="button"
      onClick={() => void stop()}
      className="flex size-8 shrink-0 items-center justify-center rounded-full bg-destructive text-white hover:brightness-110"
      title="停止生成"
      aria-label="停止"
    >
      <Square className="size-3.5 fill-current" strokeWidth={0} />
    </button>
  ) : (
    <button
      type="submit"
      disabled={!canSend || sending}
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-full transition-colors",
        canSend && !sending
          ? "bg-primary text-primary-foreground hover:opacity-90"
          : "cursor-not-allowed bg-muted text-faint-foreground",
      )}
      title="发送消息 (Enter)"
      aria-label="发送"
    >
      <ArrowUp className="size-4" strokeWidth={2.25} />
    </button>
  );

  return (
    <form onSubmit={onSubmit} className="relative shrink-0 bg-transparent px-0 pt-1 pb-4">
      <div className="chat-column relative">
        {slashOpen ? (
          <div className="absolute right-0 bottom-full left-0 z-20 mb-2 max-h-64 overflow-hidden overflow-y-auto rounded-2xl border border-surface-border bg-surface-raised shadow-[var(--menu-shadow)]">
            <div className="border-b border-border px-3 py-2 text-micro font-medium tracking-wide text-muted-foreground uppercase">
              斜杠命令
            </div>
            {slashItems.map((item, idx) => (
              <button
                key={`${item.kind}-${item.name}`}
                type="button"
                onMouseDown={(ev) => {
                  ev.preventDefault();
                  applySlash(item);
                }}
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-2 text-left text-body transition-colors",
                  idx === slashIndex ? "bg-surface-selected" : "hover:bg-surface-hover",
                )}
              >
                <span
                  className={cn(
                    "rounded-md px-2 py-0.5 font-mono text-micro font-medium",
                    item.kind === "skill"
                      ? "bg-brand/10 text-brand"
                      : "bg-muted text-foreground",
                  )}
                >
                  {item.slash || `/${item.name}`}
                </span>
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-label font-medium text-foreground">
                    {item.name || ""}
                  </span>
                  <span className="truncate text-micro text-muted-foreground">
                    {item.desc || ""}
                  </span>
                </div>
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
            "relative border bg-surface transition-all",
            expanded
              ? [
                  "flex flex-col rounded-2xl shadow-[var(--floating-shadow)]",
                  "focus-within:border-brand/50 focus-within:ring-2 focus-within:ring-ring/15",
                ]
              : [
                  "flex h-11 items-center gap-1.5 rounded-full px-1.5",
                  "shadow-[0_1px_2px_rgb(15_23_42/0.06)]",
                  "focus-within:border-brand/40",
                ],
            dragOver ? "border-brand ring-2 ring-ring/20" : "border-surface-border",
          )}
        >
          {expanded && attachments.length > 0 ? (
            <div className="flex flex-wrap gap-2 px-3 pt-3">
              {attachments.map((att, idx) => (
                <div
                  key={`${att.type}-${att.path || att.url || idx}`}
                  className="group/att relative flex max-w-[220px] items-center gap-2 rounded-xl border border-surface-border bg-muted py-1.5 pr-1.5 pl-1.5"
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
                        <Link2 className="size-4" strokeWidth={1.75} />
                      ) : (
                        <FileText className="size-4" strokeWidth={1.75} />
                      )}
                    </span>
                  )}
                  <span className="min-w-0 flex-1 truncate text-caption text-foreground">
                    {att.name || att.url || att.path || "附件"}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(idx)}
                    className="rounded-md p-0.5 text-faint-foreground hover:bg-surface-hover hover:text-destructive"
                    aria-label="移除附件"
                  >
                    <X className="size-3.5" strokeWidth={1.75} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          {!expanded ? (
            <div ref={attachRef} className="relative shrink-0">
              <button
                type="button"
                onClick={() => setAttachMenuOpen((v) => !v)}
                className={cn(
                  "flex size-8 items-center justify-center rounded-full transition-colors",
                  attachMenuOpen
                    ? "bg-surface-selected text-foreground"
                    : "bg-muted text-muted-foreground hover:bg-surface-hover hover:text-foreground",
                )}
                title="添加附件"
                aria-label="添加附件"
              >
                <Plus className="size-4" strokeWidth={2} />
              </button>
              {attachMenu}
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
            placeholder={expanded ? "继续对话…" : "Send follow-up"}
            className={cn(
              "resize-none bg-transparent text-body text-foreground outline-none placeholder:text-faint-foreground",
              expanded
                ? "min-h-[44px] w-full px-4 pt-3.5 pb-2 leading-relaxed"
                : "h-7 min-h-0 flex-1 py-1 leading-7",
            )}
          />

          {expanded ? (
            <div className="flex items-center justify-between gap-2 px-2.5 pb-2.5">
              <div ref={attachRef} className="relative">
                <button
                  type="button"
                  onClick={() => setAttachMenuOpen((v) => !v)}
                  className={cn(
                    "flex size-8 items-center justify-center rounded-full transition-colors",
                    attachMenuOpen
                      ? "bg-surface-selected text-foreground"
                      : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
                  )}
                  title="添加附件"
                  aria-label="添加附件"
                >
                  <Plus className="size-4" strokeWidth={2} />
                </button>
                {attachMenu}
              </div>
              <div className="flex items-center gap-1.5">
                <ModelSelect />
                {sendBtn}
              </div>
            </div>
          ) : (
            <div className="flex shrink-0 items-center gap-0.5 pr-0.5">
              <ModelSelect />
              {running ? sendBtn : null}
            </div>
          )}

          {dragOver ? (
            <div
              className={cn(
                "pointer-events-none absolute inset-0 flex items-center justify-center border-2 border-dashed border-brand bg-brand/5",
                expanded ? "rounded-2xl" : "rounded-full",
              )}
            >
              <span className="text-label font-medium text-brand">松开以添加附件</span>
            </div>
          ) : null}
        </div>
      </div>
    </form>
  );
}
