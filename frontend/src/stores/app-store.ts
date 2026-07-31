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

export type DisplayMessage =
  | { id: string; role: "user"; content: string; images?: ChatImage[] }
  | {
      id: string;
      role: "assistant";
      content: string;
      streaming?: boolean;
      elapsedMs?: number;
    }
  | { id: string; role: "meta"; content: string; accent?: string };

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
  loadHistory: (events: ChatEvent[]) => void;
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
  return Math.max(50, Math.min(100, Math.round(Number(pct) || 85)));
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
      if (streamingId) {
        return {
          messages: messages.map((m) =>
            m.id === streamingId && m.role === "assistant"
              ? {
                  ...m,
                  content: ev.content || m.content,
                  streaming: false,
                  elapsedMs: ev.elapsed_ms,
                }
              : m,
          ),
          streamingId: null,
          toolStatus: "",
        };
      }
      if (ev.content) {
        return {
          messages: [
            ...messages,
            {
              id: nextId("assistant"),
              role: "assistant",
              content: ev.content,
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
  approval: null,
  modelLabel: "—",
  slashCatalog: [],
  inputHistory: [],
  settingsOpen: false,
  themeId: "default",
  appearance: "dark",
  fontId: "system",
  chatWidthPct: 85,
  activeView: "chat",
  composerPrefill: null,
  sidebarCollapsed: false,

  setReady: (ready) => set({ ready }),
  setBootError: (bootError) => set({ bootError }),
  setApproval: (approval) => set({ approval }),
  setSessions: (sessions) => set({ sessions }),
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

    const chatWidthPct = applyChatWidthToDom(state.chat_width_pct ?? 85);

    set({
      ready: true,
      bootError: null,
      title: state.title,
      welcome: state.welcome,
      statusText: state.status_text,
      themeVariables: state.theme_variables || {},
      workspace: state.workspace,
      sessions: state.sessions || [],
      messages,
      streamingId,
      toolStatus: "",
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
    if (ev.type === "running") {
      set({ running: !!ev.running });
      return;
    }
    if (ev.type === "status") {
      set({ statusText: ev.text || "" });
      return;
    }
    if (ev.type === "approval") {
      set({ approval: ev.description || "" });
      return;
    }
    if (ev.type === "theme") {
      get().applyTheme(ev.variables || {});
      return;
    }

    const { messages, streamingId } = get();
    const next = reduceChatEvent(messages, streamingId, ev);
    set({
      messages: next.messages,
      streamingId: next.streamingId,
      ...(next.toolStatus !== undefined ? { toolStatus: next.toolStatus } : {}),
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
    set({ messages, streamingId, toolStatus });
  },
}));
