import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/App";
import { waitForPywebview } from "@/bridge/api";
import { useAppStore } from "@/stores/app-store";
import type { BridgeEvent, ChatEvent } from "@/bridge/types";
import "@/styles/tokens.css";

function installChatAppBridge(): void {
  const handleEvent = (ev: BridgeEvent) => {
    useAppStore.getState().handleBridgeEvent(ev);
  };
  const handleEvents = (events: BridgeEvent[]) => {
    useAppStore.getState().handleBridgeEvents(events || []);
  };
  const loadHistory = (events: ChatEvent[]) => {
    useAppStore.getState().loadHistory(events || []);
  };

  window.ChatApp = { handleEvent, handleEvents, loadHistory };
  // 兼容 WebChatBridge.load_history → window.ChatUI.loadHistory
  window.ChatUI = { loadHistory, handleEvent };
}

async function bootstrap(): Promise<void> {
  installChatAppBridge();
  try {
    const api = await waitForPywebview();
    const state = await api.get_initial_state();
    useAppStore.getState().applyInitialState(state);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    useAppStore.getState().setBootError(message);
  }
}

void bootstrap();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
