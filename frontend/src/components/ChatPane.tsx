import { useEffect, useRef, useState } from "react";
import { Bot, Check, Clock3, Copy, Sparkles } from "lucide-react";
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
      className={cn(
        "inline-flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-micro transition",
        "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
      )}
      title={label}
    >
      {copied ? (
        <Check className="size-3" strokeWidth={2} />
      ) : (
        <Copy className="size-3" strokeWidth={1.75} />
      )}
      {copied ? "已复制" : label}
    </button>
  );
}

function MessageBubble({ msg }: { msg: DisplayMessage }) {
  if (msg.role === "meta") {
    return (
      <div className="flex justify-center px-4 py-2 animate-fade-in-up">
        <span className="inline-flex items-center rounded-full border border-surface-border bg-surface/80 px-3 py-1 text-caption text-muted-foreground shadow-[var(--surface-shadow)] backdrop-blur-sm">
          {msg.content}
        </span>
      </div>
    );
  }

  const isUser = msg.role === "user";
  const streaming = msg.role === "assistant" && msg.streaming;
  const elapsed = msg.role === "assistant" ? formatElapsed(msg.elapsedMs) : "";

  return (
    <div
      className={cn(
        "group flex gap-2.5 px-4 py-1.5 animate-fade-in-up",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      {!isUser ? (
        <div
          className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand/10 text-brand"
          aria-hidden
        >
          <Bot className="size-3.5" strokeWidth={1.75} />
        </div>
      ) : null}

      <div
        className={cn(
          "flex min-w-0 flex-col gap-1",
          isUser ? "items-end max-w-[min(640px,82%)]" : "items-start max-w-[min(720px,88%)]",
        )}
      >
        <div
          className={cn(
            "relative w-full break-words text-body leading-[1.65]",
            isUser
              ? [
                  "rounded-[var(--radius-bubble)] rounded-br-md",
                  "bg-primary px-4 py-2.5 text-primary-foreground",
                  "shadow-[0_1px_2px_rgba(0,113,227,0.22)]",
                ]
              : [
                  "rounded-[var(--radius-bubble)] rounded-tl-md",
                  "border border-surface-border bg-surface/90 px-4 py-3 text-foreground",
                  "shadow-[var(--surface-shadow)] backdrop-blur-sm",
                ],
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
                    className="max-h-48 max-w-full rounded-xl object-cover ring-1 ring-white/25"
                  />
                );
              })}
            </div>
          ) : null}

          {isUser ? (
            <div className="whitespace-pre-wrap">{msg.content}</div>
          ) : streaming ? (
            <span className="whitespace-pre-wrap text-foreground/90">
              {msg.content || (
                <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                  <span className="inline-flex gap-1">
                    <span className="size-1.5 animate-pulse rounded-full bg-brand" />
                    <span
                      className="size-1.5 animate-pulse rounded-full bg-brand"
                      style={{ animationDelay: "120ms" }}
                    />
                    <span
                      className="size-1.5 animate-pulse rounded-full bg-brand"
                      style={{ animationDelay: "240ms" }}
                    />
                  </span>
                  思考中
                </span>
              )}
              {msg.content ? (
                <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse rounded-sm bg-brand align-middle" />
              ) : null}
            </span>
          ) : (
            <Markdown content={msg.content || ""} />
          )}
        </div>

        {(elapsed && !streaming) || (!streaming && msg.content) ? (
          <div
            className={cn(
              "flex items-center gap-2 px-1",
              "opacity-0 transition-opacity duration-200 group-hover:opacity-100",
              isUser ? "flex-row-reverse" : "flex-row",
            )}
          >
            {elapsed && !streaming ? (
              <span className="inline-flex items-center gap-1 text-micro text-faint-foreground">
                <Clock3 className="size-3" strokeWidth={1.75} />
                {elapsed}
              </span>
            ) : null}
            {!streaming && msg.content ? (
              <>
                <CopyBtn label="复制" text={msg.content} />
                {msg.role === "assistant" ? (
                  <CopyBtn label="MD" text={msg.content} />
                ) : null}
              </>
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
    <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-transparent">
      <div className="min-h-0 flex-1 overflow-y-auto py-5">
        <div className="chat-column">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center gap-4 px-6 pt-24 pb-10 text-center animate-fade-in-up">
              <div className="flex size-14 items-center justify-center rounded-[20px] bg-brand text-brand-foreground shadow-[0_8px_24px_rgba(0,113,227,0.28)]">
                <Sparkles className="size-6" strokeWidth={1.75} />
              </div>
              <div className="space-y-2">
                <h2 className="text-[22px] font-semibold tracking-tight text-foreground">
                  个人助理
                </h2>
                <p className="mx-auto max-w-md text-body leading-relaxed text-muted-foreground whitespace-pre-line">
                  {welcome ||
                    "欢迎使用个人助理 Agent。Enter 发送，Shift+Enter 换行。\n输入 / 查看命令。"}
                </p>
              </div>
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} msg={m} />)
          )}

          {toolStatus ? (
            <div className="flex items-center gap-2.5 px-4 py-2 animate-fade-in-up">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand/10 text-brand">
                <Bot className="size-3.5" strokeWidth={1.75} />
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-surface-border bg-surface/80 px-3 py-1.5 text-caption text-muted-foreground shadow-[var(--surface-shadow)] backdrop-blur-sm">
                <span className="size-1.5 animate-pulse rounded-full bg-brand" />
                {toolStatus}
              </div>
            </div>
          ) : null}

          <div ref={bottomRef} />
        </div>
      </div>
    </main>
  );
}
