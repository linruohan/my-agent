import { useEffect, useRef, useState } from "react";
import { getApi } from "@/bridge/api";
import { useAppStore } from "@/stores/app-store";
import { cn } from "@/lib/cn";

export function ChatWidthControl() {
  const chatWidthPct = useAppStore((s) => s.chatWidthPct);
  const setChatWidthPct = useAppStore((s) => s.setChatWidthPct);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const onChange = (raw: number) => {
    const value = setChatWidthPct(raw);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveTimer.current = null;
      const api = getApi();
      if (!api?.save_chat_width) return;
      void api.save_chat_width(value).catch((err) => {
        console.warn("save_chat_width failed:", err);
      });
    }, 280);
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "h-8 rounded-lg px-2.5 text-label transition",
          open
            ? "bg-surface-selected text-foreground"
            : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
        )}
        title="聊天宽度"
        aria-label="聊天宽度"
      >
        宽度
      </button>
      {open ? (
        <div className="absolute top-full right-0 z-30 mt-2 w-56 rounded-xl border border-surface-border bg-surface p-3 shadow-[var(--menu-shadow)]">
          <div className="mb-2 flex items-center justify-between text-caption text-muted-foreground">
            <span>聊天宽度</span>
            <span className="tabular-nums text-foreground">{chatWidthPct}%</span>
          </div>
          <input
            type="range"
            min={50}
            max={100}
            step={5}
            value={chatWidthPct}
            onChange={(e) => onChange(Number(e.target.value))}
            className="w-full accent-[var(--brand)]"
          />
        </div>
      ) : null}
    </div>
  );
}
