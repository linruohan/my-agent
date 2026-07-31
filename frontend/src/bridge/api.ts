import type { AppApi } from "./types";

export function getApi(): AppApi | null {
  return window.pywebview?.api ?? null;
}

export function waitForPywebview(timeoutMs = 15000): Promise<AppApi> {
  const existing = getApi();
  if (existing) return Promise.resolve(existing);

  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error("pywebview API 超时未就绪"));
    }, timeoutMs);

    const onReady = () => {
      cleanup();
      const api = getApi();
      if (!api) {
        reject(new Error("pywebviewready 已触发但 api 不可用"));
        return;
      }
      resolve(api);
    };

    const cleanup = () => {
      window.clearTimeout(timer);
      window.removeEventListener("pywebviewready", onReady);
    };

    window.addEventListener("pywebviewready", onReady);
  });
}
