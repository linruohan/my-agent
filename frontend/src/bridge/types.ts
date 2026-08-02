/**
 * pywebview bridge 契约：与 src/ui/api/*、WebChatBridge 事件对齐。
 * Python → JS：window.ChatApp.handleEvent(ev)
 * JS → Python：window.pywebview.api.<method>(...)
 */

export type ThemeVariables = Record<string, string>;

export type SessionSummary = {
  id: string;
  title: string;
  active: boolean;
};

export type TaskStatus = "pending" | "planned" | "expired" | "done";

export type TaskItem = {
  id: number;
  title: string;
  content: string;
  due_at?: string | null;
  remind_at?: string | null;
  created_at: string;
  updated_at: string;
  tags: string[];
  status: TaskStatus | string;
  owner?: string | null;
  attachments?: { type: string; value: string }[];
};

export type SlashCatalogItem = {
  kind?: "tool" | "skill" | string;
  name: string;
  label?: string;
  desc?: string;
  slash?: string;
  path?: string;
};

export type ThemeCatalogItem = {
  id: string;
  name: string;
  modes: string[];
};

export type ProviderListItem = {
  id: string;
  display_name: string;
  model: string;
  active: boolean;
  deletable: boolean;
  type: string;
  base_url: string;
  temperature: number;
  has_api_key: boolean;
  is_builtin: boolean;
};

export type SettingsData = {
  theme_catalog: ThemeCatalogItem[];
  theme_id: string;
  appearance: string;
  font_catalog?: { id: string; name: string }[];
  font_id: string;
  current_provider: string;
  provider_list: ProviderListItem[];
  skill_dirs: string;
  task_owner_name: string;
};

export type WorkspaceInfo = {
  owner_name: string;
  work_dir: string;
  work_dir_label: string;
};

export type ComposerMeta = {
  session_short: string;
  current_provider: string;
  current_model: string;
  provider_type: string;
  provider_base_url: string;
};

export type ChatImage = {
  path?: string;
  data_url?: string;
  name?: string;
};

export type AttachmentPayload = {
  type: "image" | "file" | "link" | string;
  path?: string;
  url?: string;
  name?: string;
};

export type SendMessagePayload = {
  text: string;
  attachments?: AttachmentPayload[];
};

export type InitialState = {
  title: string;
  theme_variables: ThemeVariables;
  theme_id: string;
  appearance: string;
  font_id: string;
  status_text: string;
  welcome: string;
  composer_meta: ComposerMeta;
  chat_width_pct: number;
  workspace: WorkspaceInfo;
  sessions: SessionSummary[];
  slash_catalog: SlashCatalogItem[];
  input_history: string[];
  skill_dirs: string[];
  session_events: ChatEvent[];
  history_total?: number;
  history_oldest_seq?: number | null;
  history_has_more?: boolean;
};

export type OkSessionsResult = {
  ok: boolean;
  error?: string;
  active_id?: string;
  /** 历史已由 Python WebChatBridge 推送，前端勿再 loadHistory */
  history_via_bridge?: boolean;
  events?: ChatEvent[];
  sessions?: SessionSummary[];
  history_total?: number;
  history_truncated?: boolean;
  history_oldest_seq?: number | null;
  history_has_more?: boolean;
};

export type LoadEarlierResult = {
  ok: boolean;
  error?: string;
  events?: ChatEvent[];
  oldest_seq?: number | null;
  newest_seq?: number | null;
  has_more?: boolean;
  history_total?: number;
};

export type UiEvent =
  | { type: "running"; running: boolean }
  | { type: "status"; text: string }
  | { type: "approval"; description: string }
  | { type: "theme"; variables: ThemeVariables };

export type ChatEvent =
  | { type: "clear" }
  | { type: "user"; content: string; images?: ChatImage[] }
  | { type: "assistant_start"; content?: string }
  | { type: "assistant_token"; content: string }
  | {
      type: "assistant_end";
      content: string;
      content_format?: string;
      elapsed_ms?: number;
    }
  | { type: "assistant_reset" }
  | { type: "meta"; content: string; accent?: string }
  | { type: "tool_status"; content: string; accent?: string };

export type BridgeEvent = UiEvent | ChatEvent;

/** pywebview js_api 方法面（按需扩展，与 AppApi Mixin 对齐） */
export type AppApi = {
  get_initial_state: () => Promise<InitialState>;
  send_message: (payload: SendMessagePayload | string) => Promise<boolean>;
  stop_agent: () => Promise<void>;
  approval_response: (approved: boolean) => Promise<void>;

  new_session: () => Promise<OkSessionsResult>;
  list_sessions: () => Promise<{ sessions: SessionSummary[] }>;
  switch_session: (sessionId: string) => Promise<OkSessionsResult>;
  delete_session: (sessionId: string) => Promise<OkSessionsResult>;
  rename_session: (sessionId: string, title: string) => Promise<OkSessionsResult>;
  load_earlier_events: (
    sessionId: string,
    beforeSeq: number,
    limit?: number,
  ) => Promise<LoadEarlierResult>;

  get_settings_data: () => Promise<SettingsData>;
  save_settings: (payload: Record<string, unknown>) => Promise<{
    ok: boolean;
    error?: string;
    theme_variables?: ThemeVariables;
    status_text?: string;
    workspace?: WorkspaceInfo;
    composer_meta?: Partial<ComposerMeta>;
  }>;
  activate_provider: (providerId: string) => Promise<{
    ok: boolean;
    error?: string;
    provider_list?: ProviderListItem[];
    composer_meta?: Partial<ComposerMeta>;
    status_text?: string;
  }>;
  save_provider: (payload: {
    id?: string;
    display_name: string;
    type: string;
    model: string;
    base_url?: string;
    api_key?: string;
    temperature?: number;
  }) => Promise<{
    ok: boolean;
    error?: string;
    provider_list?: ProviderListItem[];
    composer_meta?: Partial<ComposerMeta>;
    status_text?: string;
  }>;
  delete_provider: (providerId: string) => Promise<{
    ok: boolean;
    error?: string;
    provider_list?: ProviderListItem[];
    composer_meta?: Partial<ComposerMeta>;
    status_text?: string;
  }>;
  get_knowledge_stats: () => Promise<{ text: string }>;
  import_knowledge: (kind: string) => Promise<{ log?: string; text?: string }>;
  pick_work_dir: () => Promise<{
    ok: boolean;
    cancelled?: boolean;
    error?: string;
    work_dir?: string;
    work_dir_label?: string;
    status_text?: string;
  }>;
  get_slash_catalog: () => Promise<SlashCatalogItem[]>;
  save_chat_width: (pct: number) => Promise<Record<string, unknown>>;
  list_provider_models: () => Promise<{
    ok: boolean;
    models: string[];
    current_model?: string;
    provider?: string;
    error?: string | null;
  }>;
  set_model: (model: string) => Promise<{
    ok: boolean;
    error?: string;
    model?: string;
    status_text?: string;
    composer_meta?: Partial<ComposerMeta>;
  }>;

  pick_input_image: () => Promise<{ ok?: boolean; paths?: string[]; error?: string }>;
  pick_input_file: () => Promise<{ ok?: boolean; paths?: string[]; error?: string }>;
  save_pasted_image: (dataB64: string) => Promise<{ ok: boolean; path?: string; error?: string }>;
  read_image_data_url: (path: string) => Promise<{ ok: boolean; data_url?: string; error?: string }>;

  copy_to_clipboard: (text: string) => Promise<boolean>;
  open_local_path: (path: string) => Promise<Record<string, unknown>>;
  check_local_paths: (paths: string[]) => Promise<Record<string, boolean>>;

  list_tasks: (includeDone?: boolean) => Promise<{
    ok?: boolean;
    tasks: TaskItem[];
    error?: string;
  }>;
  add_task: (payload: {
    title: string;
    content?: string;
    owner?: string;
    due_at?: string;
    status?: string;
    tags?: string[];
  }) => Promise<{ ok: boolean; task?: TaskItem; error?: string }>;
  update_task_status: (
    taskId: number,
    status: string,
  ) => Promise<{ ok: boolean; task?: TaskItem | null; error?: string }>;
  delete_task: (taskId: number) => Promise<{ ok: boolean; error?: string }>;
  update_task: (
    taskId: number,
    payload: Record<string, unknown>,
  ) => Promise<{ ok: boolean; task?: TaskItem | null; error?: string }>;
};

export type ChatAppBridge = {
  handleEvent: (ev: BridgeEvent) => void;
  /** 一批事件单次 set，减少流式/工具状态 IPC 后的重渲染 */
  handleEvents?: (events: BridgeEvent[]) => void;
  /** 与旧版 ChatUI.loadHistory 对齐，供 WebChatBridge 批量回放 */
  loadHistory: (events: ChatEvent[]) => void;
};

declare global {
  interface Window {
    pywebview?: {
      api: AppApi;
    };
    ChatApp?: ChatAppBridge;
    /** 兼容旧 WebChatBridge.load_history 调用 */
    ChatUI?: {
      loadHistory: (events: ChatEvent[]) => void;
      handleEvent?: (ev: BridgeEvent) => void;
    };
  }
}

export {};
