import { memo, useEffect, useRef, useState } from "react";
import { Check, Clock3, Copy, MessageSquare } from "lucide-react";
import { useAppStore, type DisplayMessage } from "@/stores/app-store";
import { Markdown } from "@/components/Markdown";
import { HtmlEmbed, looksLikeHtmlDocument } from "@/components/HtmlEmbed";
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
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-micro text-muted-foreground transition hover:bg-surface-hover hover:text-foreground"
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

function AssistantBody({ msg }: { msg: Extract<DisplayMessage, { role: "assistant" }> }) {
  const streaming = !!msg.streaming;
  const asHtml =
    !streaming &&
    (msg.format === "html" || looksLikeHtmlDocument(msg.content || ""));

  if (streaming) {
    return (
      <span className="whitespace-pre-wrap">
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
    );
  }

  if (asHtml) {
    return <HtmlEmbed html={msg.content || ""} label="工具结果" />;
  }

  return <Markdown content={msg.content || ""} />;
}

const MESSAGE_WINDOW = 80;

const MessageBubble = memo(function MessageBubble({ msg }: { msg: DisplayMessage }) {
  if (msg.role === "meta") {
    return (
      <div className="chat-msg flex justify-center px-1 py-2">
        <span className="rounded-full bg-muted px-3 py-1 text-caption text-muted-foreground">
          {msg.content}
        </span>
      </div>
    );
  }

  const isUser = msg.role === "user";
  const streaming = msg.role === "assistant" && msg.streaming;
  const elapsed = msg.role === "assistant" ? formatElapsed(msg.elapsedMs) : "";
  const isHtml =
    msg.role === "assistant" &&
    !streaming &&
    (msg.format === "html" || looksLikeHtmlDocument(msg.content || ""));

  return (
    <div
      className={cn(
        "chat-msg group flex px-1 py-1.5",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "flex min-w-0 flex-col gap-1",
          isUser
            ? "items-end max-w-[min(640px,80%)]"
            : isHtml
              ? "items-stretch w-full max-w-full"
              : "items-start max-w-[min(720px,100%)]",
        )}
      >
        <div
          className={cn(
            "break-words text-body leading-relaxed",
            isUser
              ? "rounded-2xl bg-muted px-3.5 py-2 text-foreground"
              : isHtml
                ? "w-full"
                : "px-0.5 py-0.5 text-foreground",
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
                    className="max-h-48 max-w-full rounded-lg object-cover"
                  />
                );
              })}
            </div>
          ) : null}

          {isUser ? (
            <div className="whitespace-pre-wrap">{msg.content}</div>
          ) : (
            <AssistantBody msg={msg} />
          )}
        </div>

        {(elapsed && !streaming) || (!streaming && msg.content && !isHtml) ? (
          <div
            className={cn(
              "flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100",
              isUser ? "flex-row-reverse" : "flex-row",
            )}
          >
            {elapsed && !streaming ? (
              <span className="inline-flex items-center gap-1 text-micro text-faint-foreground">
                <Clock3 className="size-3" strokeWidth={1.75} />
                {elapsed}
              </span>
            ) : null}
            {!streaming && msg.content && !isHtml ? (
              <>
                <CopyBtn label="复制" text={msg.content} />
                {msg.role === "assistant" ? (
                  <CopyBtn label="MD" text={msg.content} />
                ) : null}
              </>
            ) : null}
          </div>
        ) : elapsed && !streaming && isHtml ? (
          <div className="flex items-center gap-1 px-0.5 text-micro text-faint-foreground opacity-0 transition-opacity group-hover:opacity-100">
            <Clock3 className="size-3" strokeWidth={1.75} />
            {elapsed}
          </div>
        ) : null}
      </div>
    </div>
  );
});

export function ChatPane() {
  const messages = useAppStore((s) => s.messages);
  const welcome = useAppStore((s) => s.welcome);
  const toolStatus = useAppStore((s) => s.toolStatus);
  const streamingId = useAppStore((s) => s.streamingId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showAll, setShowAll] = useState(false);
  const prevLenRef = useRef(0);

  const hiddenCount =
    !showAll && messages.length > MESSAGE_WINDOW
      ? messages.length - MESSAGE_WINDOW
      : 0;
  const visibleMessages =
    hiddenCount > 0 ? messages.slice(hiddenCount) : messages;

  useEffect(() => {
    // 新消息到来时若仍在窗口模式，保持只渲染尾部
    if (messages.length <= MESSAGE_WINDOW) {
      setShowAll(false);
    }
  }, [messages.length]);

  useEffect(() => {
    const grew = messages.length > prevLenRef.current;
    prevLenRef.current = messages.length;
    // 流式用 auto，避免每 token smooth 滚动；仅新增消息条时用 smooth
    const behavior: ScrollBehavior =
      streamingId || !grew ? "auto" : "smooth";
    bottomRef.current?.scrollIntoView({ behavior, block: "end" });
  }, [messages, toolStatus, streamingId]);

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-page-canvas">
      <div className="min-h-0 flex-1 overflow-y-auto py-4">
        <div className="chat-column">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center gap-3 px-4 pt-24 pb-10 text-center">
              <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <MessageSquare className="size-5" strokeWidth={1.75} />
              </div>
              <h2 className="text-title-sm font-semibold text-foreground">个人助理</h2>
              <p className="mx-auto max-w-md text-body text-muted-foreground whitespace-pre-line">
                {welcome ||
                  "欢迎使用个人助理 Agent。Enter 发送，Shift+Enter 换行。\n输入 / 查看命令。"}
              </p>
            </div>
          ) : (
            <>
              {hiddenCount > 0 ? (
                <div className="flex justify-center px-1 py-3">
                  <button
                    type="button"
                    onClick={() => setShowAll(true)}
                    className="rounded-full bg-muted px-3 py-1.5 text-caption text-muted-foreground transition hover:bg-surface-hover hover:text-foreground"
                  >
                    显示更早的 {hiddenCount} 条消息
                  </button>
                </div>
              ) : null}
              {visibleMessages.map((m) => (
                <MessageBubble key={m.id} msg={m} />
              ))}
            </>
          )}

          {toolStatus ? (
            <div className="px-1 py-2">
              <div className="inline-flex items-center gap-2 rounded-full bg-muted px-3 py-1.5 text-caption text-muted-foreground">
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
