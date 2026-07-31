const STORAGE_KEY = "my-agent.pinned-sessions";

function readPins(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string" && !!x);
  } catch {
    return [];
  }
}

function writePins(ids: string[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

export function getPinnedSessionIds(): string[] {
  return readPins();
}

export function isSessionPinned(id: string): boolean {
  return readPins().includes(id);
}

export function pinSession(id: string): string[] {
  const next = [id, ...readPins().filter((x) => x !== id)];
  writePins(next);
  return next;
}

export function unpinSession(id: string): string[] {
  const next = readPins().filter((x) => x !== id);
  writePins(next);
  return next;
}

export function togglePinSession(id: string): string[] {
  return isSessionPinned(id) ? unpinSession(id) : pinSession(id);
}

/** 清理已不存在的会话 ID */
export function prunePinnedSessions(validIds: Set<string>): string[] {
  const next = readPins().filter((id) => validIds.has(id));
  writePins(next);
  return next;
}
