import { useEffect, useRef, useState } from "react";
import { useAppStore, type DisplayMessage } from "@/stores/app-store";
import { Markdown } from "@/components/Markdown";
import { copyText } from "@/lib/clipboard";
import { formatElapsed } from "@/lib/format";
import { cn } from "@/lib/cn";

function CopyBtn({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void copyText(text).then((ok) => {
          if (!ok) return;
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="rounded-md px-1.5 py-0.5 text-micro text-muted-foreground hover:bg-surface-hover hover:text-foreground"
      title={label}
    >
      {copied ? "已复制" : label}
    </button>
  );
}

function MessageBubble({ msg }: { msg: DisplayMessage }) {
  if (msg.role === "meta") {
    return (
      <div className="px-4 py-1 text-center text-caption text-muted-foreground">
        {msg.content}
      </div>
    );
  }

  const isUser = msg.role === "user";
  const streaming = msg.role === "assistant" && msg.streaming;
  const elapsed = msg.role === "assistant" ? formatElapsed(msg.elapsedMs) : "";

  return (
    <div className={cn("group flex px-4 py-2", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "relative max-w-[min(720px,92%)] break-words rounded-xl px-4 py-3 text-body leading-relaxed",
          isUser
            ? "whitespace-pre-wrap bg-brand text-brand-foreground"
            : "border border-surface-border bg-surface text-foreground shadow-[var(--surface-shadow)]",
        )}
      >
        {isUser && msg.images && msg.images.length > 0 ? (
          <div className="mb-2 flex flex-wrap gap-2">
            {msg.images.map((img, idx) => {
              const src = img.data_url || img.path;
              if (!src) return null;
              return (
                <img
                  key={`${src}-${idx}`}
                  src={src}
                  alt={img.name || "image"}
                  className="max-h-40 max-w-full rounded-lg object-cover"
                />
              );
            })}
          </div>
        ) : null}
        {isUser ? (
          msg.content
        ) : streaming ? (
          <span className="whitespace-pre-wrap">
            {msg.content || "…"}
            <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-muted-foreground align-middle" />
          </span>
        ) : (
          <Markdown content={msg.content || ""} />
        )}
        {elapsed && !streaming ? (
          <div className="mt-2 text-micro text-muted-foreground">耗时 {elapsed}</div>
        ) : null}
        {!streaming && msg.content ? (
          <div
            className={cn(
              "mt-2 flex gap-1 opacity-0 transition group-hover:opacity-100",
              isUser ? "justify-end" : "justify-start",
            )}
          >
            <CopyBtn label="复制" text={msg.content} />
            {msg.role === "assistant" ? (
              <CopyBtn label="复制 MD" text={msg.content} />
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ChatPane() {
  const messages = useAppStore((s) => s.messages);
  const welcome = useAppStore((s) => s.welcome);
  const toolStatus = useAppStore((s) => s.toolStatus);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, toolStatus]);

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-page-canvas">
      <div className="min-h-0 flex-1 overflow-y-auto py-4">
        <div className="chat-column">
          {messages.length === 0 ? (
            <div className="flex flex-col gap-3 px-6 pt-20 text-center">
              <h2 className="text-display-sm font-semibold tracking-tight text-foreground">
                个人助理
              </h2>
              <p className="mx-auto max-w-md text-body leading-relaxed text-muted-foreground">
                {welcome || "欢迎使用。输入 / 查看斜杠命令。"}
              </p>
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} msg={m} />)
          )}
          {toolStatus ? (
            <div className="px-4 py-2 text-caption text-muted-foreground">{toolStatus}</div>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </div>
    </main>
  );
}
