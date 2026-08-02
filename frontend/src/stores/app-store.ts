import { create } from "zustand";
import type {
  BridgeEvent,
  ChatEvent,
  ChatImage,
  InitialState,
  SessionSummary,
  SlashCatalogItem,
  ThemeVariables,
  WorkspaceInfo,
} from "@/bridge/types";

export type ContentFormat = "markdown" | "html";

export type DisplayMessage =
  | { id: string; role: "user"; content: string; images?: ChatImage[] }
  | {
      id: string;
      role: "assistant";
      content: string;
      format?: ContentFormat;
      streaming?: boolean;
      elapsedMs?: number;
    }
  | { id: string; role: "meta"; content: string; accent?: string };

function resolveContentFormat(
  format: string | undefined,
  content: string,
): ContentFormat {
  if (format === "html") return "html";
  if (format === "markdown") {
    // 历史事件可能漏掉 format，对完整 HTML 文档兜底
    const head = (content || "").trimStart().slice(0, 200).toLowerCase();
    if (
      head.startsWith("<!doctype html") ||
      head.startsWith("<html") ||
      (head.includes("wx-wrap") && head.includes("<style"))
    ) {
      return "html";
    }
    return "markdown";
  }
  const head = (content || "").trimStart().slice(0, 200).toLowerCase();
  if (
    head.startsWith("<!doctype html") ||
    head.startsWith("<html") ||
    (head.includes("wx-wrap") && head.includes("<style"))
  ) {
    return "html";
  }
  return "markdown";
}

export type MainView = "chat" | "tasks" | "skills" | "calendar" | "knowledge";

type AppStore = {
  ready: boolean;
  bootError: string | null;
  title: string;
  welcome: string;
  statusText: string;
  running: boolean;
  themeVariables: ThemeVariables;
  workspace: WorkspaceInfo | null;
  sessions: SessionSummary[];
  messages: DisplayMessage[];
  streamingId: string | null;
  toolStatus: string;
  historyOldestSeq: number | null;
  historyHasMore: boolean;
  historyTotal: number;
  historyLoading: boolean;
  approval: string | null;
  modelLabel: string;
  slashCatalog: SlashCatalogItem[];
  inputHistory: string[];
  settingsOpen: boolean;
  themeId: string;
  appearance: string;
  fontId: string;
  chatWidthPct: number;
  activeView: MainView;
  composerPrefill: string | null;
  sidebarCollapsed: boolean;

  applyInitialState: (state: InitialState) => void;
  applyTheme: (variables: ThemeVariables) => void;
  handleBridgeEvent: (ev: BridgeEvent) => void;
  handleBridgeEvents: (events: BridgeEvent[]) => void;
  loadHistory: (events: ChatEvent[]) => void;
  prependHistory: (
    events: ChatEvent[],
    meta?: { oldestSeq?: number | null; hasMore?: boolean; total?: number },
  ) => void;
  setHistoryMeta: (meta: {
    oldestSeq?: number | null;
    hasMore?: boolean;
    total?: number;
  }) => void;
  setHistoryLoading: (loading: boolean) => void;
  setSessions: (sessions: SessionSummary[]) => void;
  setApproval: (description: string | null) => void;
  setBootError: (msg: string | null) => void;
  setReady: (ready: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setWorkspace: (workspace: WorkspaceInfo | null) => void;
  setModelLabel: (model: string) => void;
  setSlashCatalog: (items: SlashCatalogItem[]) => void;
  pushInputHistory: (text: string) => void;
  setActiveView: (view: MainView) => void;
  setComposerPrefill: (text: string | null) => void;
  setChatWidthPct: (pct: number) => number;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebarCollapsed: () => void;
  patchFromSettings: (patch: {
    themeVariables?: ThemeVariables;
    statusText?: string;
    workspace?: WorkspaceInfo;
    modelLabel?: string;
    themeId?: string;
    appearance?: string;
    fontId?: string;
  }) => void;
};

let msgSeq = 0;
function nextId(prefix: string): string {
  msgSeq += 1;
  return `${prefix}-${msgSeq}`;
}

function applyThemeToDom(variables: ThemeVariables): void {
  const root = document.documentElement;
  Object.entries(variables).forEach(([key, val]) => {
    root.style.setProperty(key, val);
  });

  // 将旧主题变量桥接到 Multica 式 surface token
  const bgApp = variables["--bg-app"];
  const bgSidebar = variables["--bg-sidebar"];
  const bgPanel = variables["--bg-panel"];
  const fg = variables["--fg"];
  const muted = variables["--fg-muted"];
  const accent = variables["--accent"];
  const accentFg = variables["--accent-fg"];
  const border = variables["--border"];
  if (bgApp) root.style.setProperty("--page-canvas", bgApp);
  if (bgSidebar) {
    root.style.setProperty("--app-shell", bgSidebar);
    root.style.setProperty("--sidebar", bgSidebar);
  }
  if (bgPanel) root.style.setProperty("--surface", bgPanel);
  if (fg) root.style.setProperty("--foreground", fg);
  if (muted) root.style.setProperty("--muted-foreground", muted);
  if (accent) root.style.setProperty("--brand", accent);
  if (accentFg) root.style.setProperty("--brand-foreground", accentFg);
  if (border) {
    root.style.setProperty("--border", border);
    root.style.setProperty("--surface-border", border);
  }

  const mode = variables["--theme-mode"] || "dark";
  root.dataset.themeMode = mode;
  root.style.colorScheme = mode === "light" ? "light" : "dark";
}

function clampChatWidth(pct: number): number {
  return Math.max(50, Math.min(100, Math.round(Number(pct) || 100)));
}

function applyChatWidthToDom(pct: number): number {
  const value = clampChatWidth(pct);
  document.documentElement.style.setProperty("--chat-width-pct", `${value}%`);
  return value;
}

function reduceChatEvent(
  messages: DisplayMessage[],
  streamingId: string | null,
  ev: ChatEvent,
): { messages: DisplayMessage[]; streamingId: string | null; toolStatus?: string } {
  switch (ev.type) {
    case "clear":
      return { messages: [], streamingId: null, toolStatus: "" };
    case "user":
      return {
        messages: [
          ...messages,
          {
            id: nextId("user"),
            role: "user",
            content: ev.content,
            images: ev.images,
          },
        ],
        streamingId,
      };
    case "assistant_start": {
      const id = nextId("assistant");
      return {
        messages: [
          ...messages,
          {
            id,
            role: "assistant",
            content: ev.content || "",
            streaming: true,
          },
        ],
        streamingId: id,
      };
    }
    case "assistant_token": {
      if (!streamingId) {
        const id = nextId("assistant");
        return {
          messages: [
            ...messages,
            { id, role: "assistant", content: ev.content || "", streaming: true },
          ],
          streamingId: id,
        };
      }
      // 流式消息通常在末尾：避免整表 map
      const last = messages[messages.length - 1];
      if (last && last.id === streamingId && last.role === "assistant") {
        const next = messages.slice(0, -1);
        next.push({ ...last, content: last.content + (ev.content || "") });
        return { messages: next, streamingId };
      }
      return {
        messages: messages.map((m) =>
          m.id === streamingId && m.role === "assistant"
            ? { ...m, content: m.content + (ev.content || "") }
            : m,
        ),
        streamingId,
      };
    }
    case "assistant_end": {
      const content = ev.content || "";
      const format = resolveContentFormat(ev.content_format, content || "");
      if (streamingId) {
        return {
          messages: messages.map((m) =>
            m.id === streamingId && m.role === "assistant"
              ? {
                  ...m,
                  content: content || m.content,
                  format: resolveContentFormat(
                    ev.content_format,
                    content || m.content,
                  ),
                  streaming: false,
                  elapsedMs: ev.elapsed_ms,
                }
              : m,
          ),
          streamingId: null,
          toolStatus: "",
        };
      }
      if (content) {
        return {
          messages: [
            ...messages,
            {
              id: nextId("assistant"),
              role: "assistant",
              content,
              format,
              elapsedMs: ev.elapsed_ms,
            },
          ],
          streamingId: null,
          toolStatus: "",
        };
      }
      return { messages, streamingId: null, toolStatus: "" };
    }
    case "assistant_reset":
      if (!streamingId) return { messages, streamingId };
      return {
        messages: messages.filter((m) => m.id !== streamingId),
        streamingId: null,
      };
    case "meta":
      return {
        messages: [
          ...messages,
          {
            id: nextId("meta"),
            role: "meta",
            content: ev.content,
            accent: ev.accent,
          },
        ],
        streamingId,
      };
    case "tool_status":
      return { messages, streamingId, toolStatus: ev.content || "" };
    default:
      return { messages, streamingId };
  }
}

export const useAppStore = create<AppStore>((set, get) => ({
  ready: false,
  bootError: null,
  title: "个人助理 Agent",
  welcome: "",
  statusText: "",
  running: false,
  themeVariables: {},
  workspace: null,
  sessions: [],
  messages: [],
  streamingId: null,
  toolStatus: "",
  historyOldestSeq: null,
  historyHasMore: false,
  historyTotal: 0,
  historyLoading: false,
  approval: null,
  modelLabel: "—",
  slashCatalog: [],
  inputHistory: [],
  settingsOpen: false,
  themeId: "default",
  appearance: "dark",
  fontId: "system",
  chatWidthPct: 100,
  activeView: "chat",
  composerPrefill: null,
  sidebarCollapsed: false,

  setReady: (ready) => set({ ready }),
  setBootError: (bootError) => set({ bootError }),
  setApproval: (approval) => set({ approval }),
  setSessions: (sessions) => set({ sessions: (sessions || []).filter((s) => !!s?.id) }),
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  setWorkspace: (workspace) => set({ workspace }),
  setModelLabel: (modelLabel) => set({ modelLabel }),
  setSlashCatalog: (slashCatalog) => set({ slashCatalog }),
  setActiveView: (activeView) => set({ activeView }),
  setComposerPrefill: (composerPrefill) => set({ composerPrefill }),
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  toggleSidebarCollapsed: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setChatWidthPct: (pct) => {
    const chatWidthPct = applyChatWidthToDom(pct);
    set({ chatWidthPct });
    return chatWidthPct;
  },
  pushInputHistory: (text) =>
    set((s) => {
      const trimmed = text.trim();
      if (!trimmed) return s;
      const next = [trimmed, ...s.inputHistory.filter((x) => x !== trimmed)].slice(0, 50);
      return { inputHistory: next };
    }),
  patchFromSettings: (patch) => {
    if (patch.themeVariables) applyThemeToDom(patch.themeVariables);
    set({
      ...(patch.themeVariables ? { themeVariables: patch.themeVariables } : {}),
      ...(patch.statusText !== undefined ? { statusText: patch.statusText } : {}),
      ...(patch.workspace ? { workspace: patch.workspace } : {}),
      ...(patch.modelLabel ? { modelLabel: patch.modelLabel } : {}),
      ...(patch.themeId ? { themeId: patch.themeId } : {}),
      ...(patch.appearance ? { appearance: patch.appearance } : {}),
      ...(patch.fontId ? { fontId: patch.fontId } : {}),
    });
  },

  applyTheme: (variables) => {
    applyThemeToDom(variables);
    set({ themeVariables: variables });
  },

  applyInitialState: (state) => {
    applyThemeToDom(state.theme_variables || {});
    document.title = state.title || document.title;

    let messages: DisplayMessage[] = [];
    let streamingId: string | null = null;
    for (const ev of state.session_events || []) {
      const next = reduceChatEvent(messages, streamingId, ev);
      messages = next.messages;
      streamingId = next.streamingId;
    }

    const chatWidthPct = applyChatWidthToDom(state.chat_width_pct ?? 100);
    const sessions = (state.sessions || []).filter((s) => !!s?.id);

    set({
      ready: true,
      bootError: null,
      title: state.title,
      welcome: state.welcome,
      statusText: state.status_text,
      themeVariables: state.theme_variables || {},
      workspace: state.workspace,
      sessions,
      messages,
      streamingId,
      toolStatus: "",
      historyOldestSeq:
        state.history_oldest_seq === undefined || state.history_oldest_seq === null
          ? null
          : Number(state.history_oldest_seq),
      historyHasMore: !!state.history_has_more,
      historyTotal: Number(state.history_total || 0),
      historyLoading: false,
      modelLabel: state.composer_meta?.current_model || "—",
      slashCatalog: state.slash_catalog || [],
      inputHistory: state.input_history || [],
      themeId: state.theme_id || "default",
      appearance: state.appearance || "dark",
      fontId: state.font_id || "system",
      chatWidthPct,
    });
  },

  handleBridgeEvent: (ev) => {
    get().handleBridgeEvents([ev]);
  },

  handleBridgeEvents: (events) => {
    if (!events?.length) return;
    let { messages, streamingId, toolStatus, running, statusText, approval } = get();
    let themeVars: ThemeVariables | null = null;
    let touchedChat = false;
    let touchedUi = false;

    for (const ev of events) {
      if (ev.type === "running") {
        running = !!ev.running;
        touchedUi = true;
        continue;
      }
      if (ev.type === "status") {
        statusText = ev.text || "";
        touchedUi = true;
        continue;
      }
      if (ev.type === "approval") {
        approval = ev.description || "";
        touchedUi = true;
        continue;
      }
      if (ev.type === "theme") {
        themeVars = ev.variables || {};
        continue;
      }
      const next = reduceChatEvent(messages, streamingId, ev);
      messages = next.messages;
      streamingId = next.streamingId;
      if (next.toolStatus !== undefined) toolStatus = next.toolStatus;
      touchedChat = true;
    }

    if (themeVars) get().applyTheme(themeVars);
    if (!touchedChat && !touchedUi) return;
    set({
      ...(touchedChat
        ? { messages, streamingId, toolStatus }
        : {}),
      ...(touchedUi ? { running, statusText, approval } : {}),
    });
  },

  loadHistory: (events) => {
    let messages: DisplayMessage[] = [];
    let streamingId: string | null = null;
    let toolStatus = "";
    for (const ev of events || []) {
      const next = reduceChatEvent(messages, streamingId, ev);
      messages = next.messages;
      streamingId = next.streamingId;
      if (next.toolStatus !== undefined) toolStatus = next.toolStatus;
    }
    set({ messages, streamingId, toolStatus, historyLoading: false });
  },

  setHistoryMeta: (meta) => {
    set({
      ...(meta.oldestSeq !== undefined
        ? {
            historyOldestSeq:
              meta.oldestSeq === null || meta.oldestSeq === undefined
                ? null
                : Number(meta.oldestSeq),
          }
        : {}),
      ...(meta.hasMore !== undefined ? { historyHasMore: !!meta.hasMore } : {}),
      ...(meta.total !== undefined ? { historyTotal: Number(meta.total || 0) } : {}),
    });
  },

  setHistoryLoading: (historyLoading) => set({ historyLoading }),

  prependHistory: (events, meta) => {
    let prefix: DisplayMessage[] = [];
    let streamingId: string | null = null;
    for (const ev of events || []) {
      const next = reduceChatEvent(prefix, streamingId, ev);
      prefix = next.messages;
      streamingId = next.streamingId;
    }
    if (!prefix.length && !meta) return;
    const { messages } = get();
    set({
      messages: [...prefix, ...messages],
      ...(meta?.oldestSeq !== undefined
        ? {
            historyOldestSeq:
              meta.oldestSeq === null ? null : Number(meta.oldestSeq),
          }
        : {}),
      ...(meta?.hasMore !== undefined ? { historyHasMore: !!meta.hasMore } : {}),
      ...(meta?.total !== undefined
        ? { historyTotal: Number(meta.total || 0) }
        : {}),
      historyLoading: false,
    });
  },
}));
