import type { ChatEvent, OkSessionsResult, SessionSummary } from "@/bridge/types";
import { useAppStore } from "@/stores/app-store";

/** 应用 switch/new_session 结果：历史默认由 Python bridge 推送，避免二次回放。 */
export function applySessionApiResult(
  res: OkSessionsResult | null | undefined,
  setSessions?: (sessions: SessionSummary[]) => void,
): void {
  if (!res) return;
  const next = (res.sessions || []).filter((s) => !!s?.id);
  if (res.sessions) {
    if (setSessions) setSessions(next);
    else useAppStore.getState().setSessions(next);
  }
  // history_via_bridge：已由 WebChatBridge.load_history 推送，勿再 loadHistory
  if (res.history_via_bridge) return;
  if ("events" in res) {
    useAppStore.getState().loadHistory((res.events as ChatEvent[]) || []);
  }
}
