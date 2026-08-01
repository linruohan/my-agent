/** 左侧会话列表管理 */
window.SessionUI = (() => {
  let activeId = "";
  let allSessions = [];
  let searchQuery = "";
  let renameResolve = null;
  let renameSessionId = null;

  const { api, el, debounce } = window.Utils;

  function updateChatTitle(sessions) {
    const titleEl = el("chat-title");
    if (!titleEl) return;
    const active = (sessions || allSessions).find((s) => s.active);
    titleEl.textContent = active?.title || "个人助理 Agent";
  }

  function finishRename(value) {
    renameResolve?.(value);
    renameResolve = null;
    renameSessionId = null;
    el("session-rename-modal")?.close();
  }

  function openRenameDialog(sessionId, currentTitle) {
    return new Promise((resolve) => {
      const modal = el("session-rename-modal");
      const input = el("session-rename-input");
      if (!modal || !input) {
        resolve(null);
        return;
      }
      renameResolve = resolve;
      renameSessionId = sessionId;
      input.value = currentTitle || "";
      input.classList.remove("is-invalid");
      modal.showModal();
      requestAnimationFrame(() => {
        input.focus();
        input.select();
      });
    });
  }

  function bindRenameDialog() {
    const modal = el("session-rename-modal");
    const input = el("session-rename-input");
    const form = el("session-rename-form");
    if (!modal || !input || !form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const title = input.value.trim();
      if (!title) {
        input.classList.add("is-invalid");
        input.focus();
        return;
      }
      input.classList.remove("is-invalid");
      if (!api() || !renameSessionId) return;
      const res = await api().rename_session(renameSessionId, title);
      if (res?.ok) {
        allSessions = res.sessions || [];
        renderSessions(allSessions);
        finishRename(title);
      }
    });

    input.addEventListener("input", () => input.classList.remove("is-invalid"));

    el("session-rename-cancel")?.addEventListener("click", () => finishRename(null));
    modal.addEventListener("cancel", (e) => {
      e.preventDefault();
      finishRename(null);
    });
  }

  function filteredSessions() {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return allSessions;
    return allSessions.filter((s) => (s.title || "").toLowerCase().includes(q));
  }

  function renderSessions(sessions) {
    allSessions = sessions || allSessions;
    activeId = allSessions.find((s) => s.active)?.id || activeId;
    updateChatTitle(allSessions);

    const list = el("session-list");
    if (!list) return;
    list.innerHTML = "";

    const visible = filteredSessions();
    if (!visible.length && searchQuery.trim()) {
      const empty = document.createElement("div");
      empty.className = "session-empty";
      empty.textContent = "无匹配会话";
      list.appendChild(empty);
      return;
    }

    visible.forEach((s) => {
      const item = document.createElement("div");
      item.className = "session-item" + (s.active ? " active" : "");
      item.dataset.id = s.id;
      item.title = s.title;

      const label = document.createElement("span");
      label.className = "session-label";
      label.textContent = s.title;
      item.appendChild(label);

      const actions = document.createElement("span");
      actions.className = "session-actions";

      const btnRename = document.createElement("button");
      btnRename.type = "button";
      btnRename.className = "session-act";
      btnRename.textContent = "✎";
      btnRename.title = "重命名";
      btnRename.addEventListener("click", async (e) => {
        e.stopPropagation();
        await openRenameDialog(s.id, s.title);
      });

      const btnDel = document.createElement("button");
      btnDel.type = "button";
      btnDel.className = "session-act";
      btnDel.textContent = "×";
      btnDel.title = "删除";
      btnDel.addEventListener("click", async (e) => {
        e.stopPropagation();
        const ok = await window.ConfirmUI?.show(`删除后无法恢复，确定删除会话「${s.title}」？`, {
          title: "删除会话",
          confirmText: "删除",
          danger: true,
        });
        if (!ok) return;
        if (!api()) return;
        const res = await api().delete_session(s.id);
        if (res?.ok) {
          allSessions = res.sessions || [];
          renderSessions(allSessions);
          if (res.events) {
            window.ChatUI.loadHistory(res.events);
          }
        } else if (res?.error) {
          window.ChatApp?.setComposerHint(res.error);
        }
      });

      actions.appendChild(btnRename);
      actions.appendChild(btnDel);
      item.appendChild(actions);

      item.addEventListener("click", async () => {
        if (!api() || s.id === activeId) {
          window.LayoutUI?.showView?.("chat");
          return;
        }
        const res = await api().switch_session(s.id);
        if (res?.ok) {
          activeId = res.active_id || s.id;
          allSessions = res.sessions || [];
          renderSessions(allSessions);
          window.LayoutUI?.showView?.("chat");
        } else if (res?.error) {
          window.ChatApp?.setComposerHint(res.error);
        }
      });

      list.appendChild(item);
    });
  }

  function bindSearch() {
    const debouncedRender = debounce(() => renderSessions(allSessions), 150);
    el("session-search")?.addEventListener("input", (e) => {
      searchQuery = e.target.value || "";
      debouncedRender();
    });
  }

  function bindTitleRename() {
    el("chat-title-btn")?.addEventListener("click", async () => {
      const active = allSessions.find((s) => s.active);
      if (!active) return;
      await openRenameDialog(active.id, active.title);
    });
  }

  function init(state) {
    bindRenameDialog();
    bindSearch();
    bindTitleRename();
    activeId = (state.sessions || []).find((s) => s.active)?.id || "";
    allSessions = state.sessions || [];
    renderSessions(allSessions);

    el("btn-new-session")?.addEventListener("click", async () => {
      if (!api()) return;
      const res = await api().new_session();
      if (res?.ok) {
        activeId = res.active_id || "";
        allSessions = res.sessions || [];
        renderSessions(allSessions);
        window.ChatUI.clear();
        window.LayoutUI?.showView?.("chat");
        if (res.events) {
          window.ChatUI.loadHistory(res.events);
        }
        const newSession = allSessions.find((s) => s.id === activeId);
        await openRenameDialog(activeId, newSession?.title || "新会话");
      }
    });

    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        el("btn-new-session")?.click();
      }
    });
  }

  return { init, renderSessions, openRenameDialog };
})();
