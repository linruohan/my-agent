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
function autoResize(el: HTMLTextAreaElement | null) {
  if (!el) return;
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
 * - Apple 风格：毛玻璃卡片输入框 + 胶囊发送按钮 + Spring 动画
 */
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

  /* 外部预填文本（例如快捷指令跳转） */
  useEffect(() => {
    if (!composerPrefill) return;
    setText(composerPrefill);
    setComposerPrefill(null);
    requestAnimationFrame(() => {
      boxRef.current?.focus();
      autoResize(boxRef.current);
    });
  }, [composerPrefill, setComposerPrefill]);

  /* 文本变化时调整输入框高度 */
  useEffect(() => {
    autoResize(boxRef.current);
  }, [text]);

  /* 点击外部关闭附件菜单 */
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

  const readyLabel = (statusText || "就绪").replace(/^模型:[^|]*\|\s*/, "").trim();

  return (
    <form
      onSubmit={onSubmit}
      className="relative bg-page-canvas/30 px-5 pt-2 pb-4"
    >
      <div className="chat-column relative flex flex-col gap-2 animate-fade-in-up" style={{ animationDelay: "100ms" }}>
        {/* 斜杠命令弹出层：Apple 菜单风格毛玻璃 */}
        {slashOpen ? (
          <div
            className="absolute right-0 bottom-full left-0 z-20 mb-3 max-h-64 overflow-y-auto
              rounded-2xl border border-surface-border/80 bg-surface/95
              backdrop-blur-[28px] backdrop-saturate-180 -webkit-backdrop-blur-[28px] -webkit-backdrop-saturate-180
              shadow-[0_20px_60px_rgba(0,0,0,0.15),0_8px_24px_rgba(0,0,0,0.1),0_0_0_0.5px_rgba(0,0,0,0.05)]
              animate-scale-in overflow-hidden"
          >
            <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground border-b border-surface-border/60">
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
                  "flex w-full items-center gap-3 px-3 py-2.5 text-left text-body transition-all duration-200",
                  idx === slashIndex
                    ? "bg-brand/12 border-l-2 border-brand pl-[11px]"
                    : "hover:bg-surface-hover border-l-2 border-transparent pl-[11px]",
                )}
              >
                <span
                  className={cn(
                    "rounded-lg px-2 py-0.5 font-mono text-micro font-semibold",
                    item.kind === "skill"
                      ? "bg-gradient-to-br from-brand/15 to-brand-purple/10 text-brand border border-brand/20"
                      : "bg-surface-hover text-foreground border border-surface-border/70",
                  )}
                >
                  {item.slash || `/${item.name}`}
                </span>
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-[13.5px] font-medium text-foreground">
                    {item.name || ""}
                  </span>
                  <span className="truncate text-[11.5px] text-muted-foreground">
                    {item.desc || ""}
                  </span>
                </div>
              </button>
            ))}
          </div>
        ) : null}

        {/* 输入框主容器：大玻璃卡片 + 胶囊内阴影 */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => void onDrop(e)}
          className={cn(
            "relative flex min-h-[80px] flex-col rounded-[24px] pb-12",
            "bg-surface/85 backdrop-blur-[30px] backdrop-saturate-180",
            "-webkit-backdrop-blur-[30px] -webkit-backdrop-saturate-180",
            "border transition-all duration-300 ease-[cubic-bezier(0.25,1,0.5,1)]",
            "shadow-[0_8px_28px_rgba(0,0,0,0.07),0_2px_8px_rgba(0,0,0,0.04),inset_0_1px_0_rgba(255,255,255,0.9)]",
            "focus-within:border-brand/60 focus-within:bg-surface/95",
            "focus-within:shadow-[0_10px_40px_rgba(0,113,227,0.18),0_4px_14px_rgba(0,113,227,0.08),inset_0_1px_0_rgba(255,255,255,0.95)]",
            dragOver
              ? "border-brand/80 ring-2 ring-brand/25 bg-surface/95 scale-[1.005]"
              : "border-surface-border/80 hover:border-surface-border",
          )}
        >
          {/* 附件预览列表 */}
          {attachments.length > 0 ? (
            <div className="flex flex-wrap gap-2.5 px-4 pt-4">
              {attachments.map((att, idx) => (
                <div
                  key={`${att.type}-${att.path || att.url || idx}`}
                  className="group/att relative flex max-w-[220px] items-center gap-2.5
                    rounded-2xl border border-surface-border/70 bg-surface-hover/70
                    py-2 pr-2 pl-2
                    backdrop-blur transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]
                    hover:-translate-y-[1px] hover:border-brand/35
                    hover:shadow-[0_6px_16px_rgba(0,0,0,0.06)]"
                >
                  {att.type === "image" && att.preview ? (
                    <img
                      src={att.preview}
                      alt={att.name || "image"}
                      className="size-10 rounded-[10px] object-cover border border-surface-border/60"
                    />
                  ) : (
                    <span className="flex size-10 items-center justify-center rounded-[10px]
                      bg-gradient-to-br from-surface to-surface-hover
                      border border-surface-border/60 text-muted-foreground">
                      {att.type === "link" ? (
                        <Link2 className="size-4" strokeWidth={1.75} />
                      ) : (
                        <FileText className="size-4" strokeWidth={1.75} />
                      )}
                    </span>
                  )}
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-foreground">
                    {att.name || att.url || att.path || "附件"}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(idx)}
                    className="rounded-md p-0.5 text-faint-foreground opacity-70
                      transition-all duration-200
                      hover:bg-destructive/10 hover:text-destructive
                      hover:scale-[1.1] group-hover/att:opacity-100"
                    aria-label="移除附件"
                  >
                    <X className="size-3.5" strokeWidth={1.75} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          {/* 文本输入区 */}
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
            placeholder="输入消息或 / 命令… 支持粘贴图片 & 拖拽文件"
            className="min-h-[48px] w-full resize-none bg-transparent
              px-4.5 pt-3.5 pb-3 text-[14.5px] leading-[1.7] text-foreground
              outline-none placeholder:text-faint-foreground/80"
            style={{ paddingLeft: "18px", paddingRight: "18px" }}
          />

          {/* 底部工具条：附件按钮（左） + 发送/停止按钮（右） */}
          <div className="absolute right-3 bottom-3 left-3 flex items-center justify-between gap-2">
            <div ref={attachRef} className="relative">
              <button
                type="button"
                onClick={() => setAttachMenuOpen((v) => !v)}
                className={cn(
                  "flex size-9 items-center justify-center rounded-[10px]",
                  "transition-all duration-200 ease-[cubic-bezier(0.25,1,0.5,1)]",
                  "hover:scale-[1.08] active:scale-[0.95]",
                  attachMenuOpen
                    ? "bg-brand/12 text-brand shadow-[0_4px_12px_rgba(0,113,227,0.18)]"
                    : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
                )}
                title="添加附件（图片 / 文件 / 链接）"
                aria-label="添加附件"
              >
                <Paperclip className="size-[18px]" strokeWidth={1.75} />
              </button>
              {/* 附件弹出菜单：Apple 胶囊菜单 */}
              {attachMenuOpen ? (
                <div
                  className="absolute bottom-full left-0 z-30 mb-2 min-w-[160px] overflow-hidden
                    rounded-2xl border border-surface-border/70 bg-surface/95 py-1.5
                    backdrop-blur-[28px] backdrop-saturate-180
                    -webkit-backdrop-blur-[28px] -webkit-backdrop-saturate-180
                    shadow-[var(--menu-shadow)]
                    animate-scale-in origin-bottom-left"
                >
                  {[
                    { icon: ImageIcon, label: "图片", onClick: () => void pickImage() },
                    { icon: FileText, label: "文件", onClick: () => void pickFile() },
                    { icon: Link2, label: "链接", onClick: promptLink },
                  ].map((it) => (
                    <button
                      key={it.label}
                      type="button"
                      onClick={it.onClick}
                      className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px]
                        text-foreground transition-all duration-150
                        hover:bg-surface-hover"
                    >
                      <span className="flex size-7 items-center justify-center rounded-lg
                        bg-gradient-to-br from-surface-hover to-surface
                        border border-surface-border/70 text-muted-foreground">
                        <it.icon className="size-[15px]" strokeWidth={1.75} />
                      </span>
                      {it.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {/* 发送 / 停止按钮 */}
            {running ? (
              /* 运行中：显示停止按钮（红色胶囊） */
              <button
                type="button"
                onClick={() => void stop()}
                className="group flex size-9 items-center justify-center rounded-full
                  bg-gradient-to-br from-[#e5484d] to-[#c9353a] text-white
                  shadow-[0_6px_18px_rgba(229,72,77,0.4),0_2px_6px_rgba(229,72,77,0.2),inset_0_1px_0_rgba(255,255,255,0.2)]
                  transition-all duration-200 ease-[cubic-bezier(0.25,1,0.5,1)]
                  hover:scale-[1.08] hover:brightness-110
                  active:scale-[0.95]"
                title="停止生成"
                aria-label="停止"
              >
                <Square className="size-[14px] fill-current" strokeWidth={0} />
              </button>
            ) : (
              /* 空闲：显示发送按钮（蓝紫渐变胶囊） */
              <button
                type="submit"
                disabled={!canSend || sending}
                className={cn(
                  "group relative flex size-9 items-center justify-center rounded-full",
                  "transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]",
                  canSend && !sending
                    ? /* 可发送状态：蓝紫渐变胶囊 + 发光阴影 */
                      "bg-gradient-to-br from-[#0071e3] to-[#6e3bd6] text-white " +
                      "shadow-[0_6px_20px_rgba(0,113,227,0.4),0_2px_6px_rgba(110,59,214,0.25),inset_0_1px_0_rgba(255,255,255,0.25)] " +
                      "hover:scale-[1.12] hover:brightness-110 " +
                      "active:scale-[0.96] " +
                      "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:hover:brightness-100"
                    : /* 禁用状态：灰暗 */
                      "bg-surface-selected text-faint-foreground/70 cursor-not-allowed",
                )}
                title="发送消息 (Enter)"
                aria-label="发送"
              >
                {/* 内部微光高光 */}
                {canSend && !sending ? (
                  <span className="pointer-events-none absolute inset-0 rounded-full opacity-0
                    group-hover:opacity-100 transition-opacity duration-300"
                    style={{
                      background:
                        "radial-gradient(ellipse at 30% 0%, rgba(255,255,255,0.35) 0%, transparent 55%)",
                    }}
                  />
                ) : null}
                <ArrowUp className="size-[18px] relative" strokeWidth={2.25} />
              </button>
            )}
          </div>

          {/* 拖拽覆盖层 */}
          {dragOver ? (
            <div
              className="pointer-events-none absolute inset-0 flex items-center justify-center
                rounded-[24px] bg-gradient-to-br from-brand/8 via-brand-purple/5 to-transparent
                backdrop-blur-[2px] border-2 border-dashed border-brand/40
                animate-pulse"
            >
              <div className="flex flex-col items-center gap-2 rounded-2xl bg-surface/90
                px-5 py-3 border border-surface-border/60 shadow-lg">
                <span className="text-2xl">📥</span>
                <span className="text-[13px] font-semibold text-brand tracking-[-0.01em]">
                  松开以添加附件
                </span>
              </div>
            </div>
          ) : null}
        </div>

        {/* 底部状态栏：就绪/状态文字 + 会话 ID + 模型选择 */}
        <div className="flex items-center justify-between gap-3 px-1 mt-0.5">
          <div className="min-w-0 truncate text-[11.5px] text-muted-foreground flex items-center gap-1.5">
            {running ? (
              /* 运行中指示灯 */
              <>
                <span className="relative inline-flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand/70 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand" />
                </span>
                <span className="text-brand font-medium">{readyLabel || "生成中…"}</span>
              </>
            ) : (
              <>
                <span className="inline-flex h-1.5 w-1.5 rounded-full bg-success/80" />
                <span>{readyLabel || "就绪"}</span>
              </>
            )}
            <span className="text-faint-foreground/90">·</span>
            <span className="text-faint-foreground/80" title={activeSession?.id}>
              {shortSessionId}
            </span>
          </div>
          <ModelSelect />
        </div>
      </div>
    </form>
  );
}
