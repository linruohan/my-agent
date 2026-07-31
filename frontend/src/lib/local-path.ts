import { getApi } from "@/bridge/api";

const WIN_ABS_PATH = /[A-Za-z]:[\\/](?:[^\s<>"'`|]+[\\/])*[^\s<>"'`|]+/g;

export function trimPathTail(raw: string): string {
  let s = raw;
  while (s.length > 3 && /:\d+$/.test(s)) {
    s = s.replace(/:\d+$/, "");
  }
  while (s.length > 3 && /[.,;，。:!?\u3001\u3002)\]}>]$/.test(s)) {
    const ext = s.match(/(\.[A-Za-z0-9]{1,8})$/);
    if (ext && s.endsWith(ext[1])) break;
    s = s.slice(0, -1);
  }
  return s;
}

export type TextPart = { type: "text" | "path"; value: string };

export function splitTextByPaths(text: string): TextPart[] {
  const parts: TextPart[] = [];
  WIN_ABS_PATH.lastIndex = 0;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = WIN_ABS_PATH.exec(text)) !== null) {
    const raw = match[0];
    const path = trimPathTail(raw);
    if (path.length < 4) continue;
    if (match.index > last) {
      parts.push({ type: "text", value: text.slice(last, match.index) });
    }
    parts.push({ type: "path", value: path });
    last = match.index + raw.length;
  }
  if (!parts.length) return [{ type: "text", value: text }];
  if (last < text.length) parts.push({ type: "text", value: text.slice(last) });
  return parts;
}

export function extractPathsFromText(text: string): string[] {
  const found = new Set<string>();
  for (const part of splitTextByPaths(text)) {
    if (part.type === "path") found.add(part.value.replace(/:\d+$/, ""));
  }
  return [...found];
}

export async function checkLocalPaths(
  paths: string[],
): Promise<Record<string, boolean>> {
  const unique = [...new Set(paths.filter(Boolean))];
  if (!unique.length) return {};
  const api = getApi();
  if (!api?.check_local_paths) return {};
  try {
    return (await api.check_local_paths(unique)) || {};
  } catch {
    return {};
  }
}

export async function openLocalPath(path: string): Promise<{ ok: boolean; error?: string }> {
  if (!path) return { ok: false, error: "空路径" };
  const api = getApi();
  if (!api?.open_local_path) {
    return { ok: false, error: "当前环境不支持打开本地文件" };
  }
  try {
    const res = (await api.open_local_path(path)) as {
      ok?: boolean;
      error?: string;
    };
    if (!res?.ok) return { ok: false, error: res?.error || "打开失败" };
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}
