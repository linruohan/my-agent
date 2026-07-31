import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MessageSquare, MoreHorizontal, Pin } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { getApi } from "@/bridge/api";
import type { ChatEvent, SessionSummary } from "@/bridge/types";
import { confirmAction } from "@/stores/confirm-store";
import {
  getPinnedSessionIds,
  prunePinnedSessions,
  togglePinSession,
  unpinSession,
} from "@/lib/session-pins";
import { cn } from "@/lib/cn";

type MenuState = {
  id: string;
  x: number;
  y: number;
};

function SessionMenu({
  menu,
  pinned,
  onClose,
  onPin,
  onRename,
  onDelete,
}: {
  menu: MenuState;
  pinned: boolean;
  onClose: () => void;
  onPin: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={ref}
      role="menu"
      className="fixed z-[80] min-w-[140px] overflow-hidden rounded-lg border border-surface-border bg-surface py-1 shadow-[var(--menu-shadow)]"
      style={{ left: menu.x, top: menu.y }}
    >
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1.5 text-left text-label text-foreground hover:bg-surface-hover"
        onClick={onPin}
      >
        {pinned ? "取消置顶" : "置顶"}
      </button>
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1.5 text-left text-label text-foreground hover:bg-surface-hover"
        onClick={onRename}
      >
        重命名
      </button>
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1.5 text-left text-label text-destructive hover:bg-surface-hover"
        onClick={onDelete}
      >
        删除
      </button>
    </div>,
    document.body,
  );
}

/** Inbox 下的层级会话列表（嵌在左侧边栏内） */
export function SidebarSessions() {
  const sessions = useAppStore((s) => s.sessions);
  const setSessions = useAppStore((s) => s.setSessions);
  const setActiveView = useAppStore((s) => s.setActiveView);

  const [menu, setMenu] = useState<MenuState | null>(null);
  const [renameTarget, setRenameTarget] = useState<SessionSummary | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState("");
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => getPinnedSessionIds());

  useEffect(() => {
    const valid = new Set(sessions.map((s) => s.id));
    setPinnedIds(prunePinnedSessions(valid));
  }, [sessions]);

  const pinnedSet = useMemo(() => new Set(pinnedIds), [pinnedIds]);

  const pinnedSessions = useMemo(() => {
    const byId = new Map(sessions.map((s) => [s.id, s]));
    return pinnedIds.map((id) => byId.get(id)).filter(Boolean) as SessionSummary[];
  }, [sessions, pinnedIds]);

  const recentSessions = useMemo(
    () => sessions.filter((s) => !pinnedSet.has(s.id)),
    [sessions, pinnedSet],
  );

  const menuSession = menu ? sessions.find((s) => s.id === menu.id) : null;
  const menuPinned = menu ? pinnedSet.has(menu.id) : false;

  const openMenuAt = (id: string, clientX: number, clientY: number) => {
    const pad = 8;
    const w = 148;
    const h = 108;
    const x = Math.min(clientX, window.innerWidth - w - pad);
    const y = Math.min(clientY, window.innerHeight - h - pad);
    setMenu({ id, x: Math.max(pad, x), y: Math.max(pad, y) });
  };

  const applySessionResult = (res: {
    sessions?: SessionSummary[];
    events?: ChatEvent[];
    active_id?: string;
  }) => {
    const nextSessions = (res.sessions || []).filter((s) => !!s?.id);
    if (res.sessions) setSessions(nextSessions);
    // 始终用返回的 events 覆盖（含空数组），避免仍显示上一个会话内容
    if ("events" in res) {
      useAppStore.getState().loadHistory(res.events || []);
    }
  };

  const refreshSessions = async () => {
    const api = getApi();
    if (!api?.list_sessions) return;
    try {
      const res = await api.list_sessions();
      if (res?.sessions) {
        setSessions((res.sessions || []).filter((s) => !!s?.id));
      }
    } catch (err) {
      console.warn("list_sessions failed:", err);
    }
  };

  const onSwitch = async (id: string) => {
    setMenu(null);
    if (!id) {
      await refreshSessions();
      return;
    }
    setActiveView("chat");
    const current = sessions.find((s) => s.id === id);
    // 仅当 id 有效且已是当前会话时跳过；避免 null id 导致全部 active 时永远不切换
    if (current?.active && current.id) return;
    const api = getApi();
    if (!api) return;
    const res = await api.switch_session(id);
    if (!res?.ok) {
      if (res?.sessions) setSessions((res.sessions || []).filter((s) => !!s?.id));
      else await refreshSessions();
      if (res?.error && res.error !== "会话不存在") {
        window.alert(res.error);
      }
      return;
    }
    applySessionResult(res);
  };

  const onDelete = async (id: string) => {
    setMenu(null);
    const ok = await confirmAction("确定删除该会话？此操作不可恢复。", {
      title: "删除会话",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    const api = getApi();
    if (!api) return;
    const res = await api.delete_session(id);
    setPinnedIds(unpinSession(id));
    if (!res?.ok) {
      if (res?.sessions) setSessions(res.sessions);
      else await refreshSessions();
      // 「会话不存在」多为重复删除/列表过期，同步列表即可，不必弹窗打断
      if (res?.error && res.error !== "会话不存在") {
        window.alert(res.error);
      }
      return;
    }
    applySessionResult(res);
  };

  const onTogglePin = (id: string) => {
    setMenu(null);
    setPinnedIds(togglePinSession(id));
  };

  const openRename = (s: SessionSummary) => {
    setMenu(null);
    setRenameTarget(s);
    setRenameValue(s.title || "");
    setRenameError("");
  };

  const submitRename = async () => {
    const title = renameValue.trim();
    if (!title) {
      setRenameError("标题不能为空");
      return;
    }
    if (!renameTarget) return;
    const api = getApi();
    if (!api) return;
    const res = await api.rename_session(renameTarget.id, title);
    if (!res?.ok) {
      setRenameError(res?.error || "重命名失败");
      return;
    }
    if (res.sessions) setSessions(res.sessions);
    setRenameTarget(null);
  };

  const renderRow = (s: SessionSummary, pinned: boolean) => (
    <div key={s.id} className="group/session relative">
      <button
        type="button"
        onClick={() => void onSwitch(s.id)}
        onContextMenu={(e) => {
          e.preventDefault();
          openMenuAt(s.id, e.clientX, e.clientY);
        }}
        className={cn(
          "flex w-full items-center gap-2 rounded-md py-1.5 pr-7 pl-2 text-left text-caption transition",
          s.active
            ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
            : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
        )}
        title={s.title || "未命名"}
      >
        {pinned ? (
          <Pin className="size-3 shrink-0 text-brand" strokeWidth={1.75} />
        ) : (
          <MessageSquare className="size-3 shrink-0 opacity-60" strokeWidth={1.75} />
        )}
        <span className="min-w-0 flex-1 truncate">{s.title || "未命名"}</span>
      </button>
      <button
        type="button"
        className={cn(
          "absolute top-1/2 right-0.5 -translate-y-1/2 rounded-md p-0.5 text-faint-foreground",
          "opacity-0 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
          "group-hover/session:opacity-100",
          menu?.id === s.id && "opacity-100",
        )}
        onClick={(e) => {
          e.stopPropagation();
          const rect = (e.currentTarget as HTMLButtonElement).getBoundingClientRect();
          openMenuAt(s.id, rect.right, rect.bottom + 4);
        }}
        aria-label="会话菜单"
      >
        <MoreHorizontal className="size-3.5" strokeWidth={1.75} />
      </button>
    </div>
  );

  return (
    <div className="mt-0.5 mb-1 ml-3 border-l border-sidebar-accent pl-2">
      <div className="max-h-[40vh] space-y-2 overflow-y-auto pr-0.5">
        {pinnedSessions.length ? (
          <div>
            <div className="px-2 py-0.5 text-micro font-medium tracking-wide text-faint-foreground uppercase">
              Pinned
            </div>
            <div className="space-y-0.5">{pinnedSessions.map((s) => renderRow(s, true))}</div>
          </div>
        ) : null}
        <div>
          {pinnedSessions.length ? (
            <div className="px-2 py-0.5 text-micro font-medium tracking-wide text-faint-foreground uppercase">
              Recent
            </div>
          ) : null}
          <div className="space-y-0.5">{recentSessions.map((s) => renderRow(s, false))}</div>
        </div>
        {!sessions.length ? (
          <div className="px-2 py-3 text-center text-micro text-faint-foreground">暂无会话</div>
        ) : null}
      </div>

      {menu && menuSession ? (
        <SessionMenu
          menu={menu}
          pinned={menuPinned}
          onClose={() => setMenu(null)}
          onPin={() => onTogglePin(menu.id)}
          onRename={() => openRename(menuSession)}
          onDelete={() => void onDelete(menu.id)}
        />
      ) : null}

      {renameTarget ? (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-xl border border-surface-border bg-surface p-5 shadow-[var(--menu-shadow)]">
            <h3 className="text-[16px] font-semibold text-foreground">重命名会话</h3>
            <input
              autoFocus
              value={renameValue}
              onChange={(e) => {
                setRenameValue(e.target.value);
                setRenameError("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void submitRename();
                }
                if (e.key === "Escape") setRenameTarget(null);
              }}
              className="mt-3 h-9 w-full rounded-lg border border-surface-border bg-input px-3 text-body text-foreground outline-none focus:border-ring"
            />
            {renameError ? (
              <p className="mt-2 text-caption text-destructive">{renameError}</p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setRenameTarget(null)}
                className="h-8 rounded-lg border border-surface-border px-3 text-label text-foreground hover:bg-surface-hover"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void submitRename()}
                className="h-8 rounded-lg bg-primary px-3 text-label font-medium text-primary-foreground"
              >
                确定
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
