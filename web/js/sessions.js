/** 左侧会话列表管理 */
window.SessionUI = (() => {
  let activeId = "";
  let renameResolve = null;
  let renameSessionId = null;

  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function el(id) {
    return document.getElementById(id);
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
        renderSessions(res.sessions);
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

  function renderSessions(sessions) {
    const list = el("session-list");
    if (!list) return;
    list.innerHTML = "";
    (sessions || []).forEach((s) => {
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
        if (!window.confirm(`删除会话「${s.title}」？`)) return;
        if (!api()) return;
        const res = await api().delete_session(s.id);
        if (res?.ok) {
          renderSessions(res.sessions);
          if (res.events) {
            window.ChatUI.clear();
            res.events.forEach((ev) => window.ChatApp.handleEvent(ev));
          }
        } else if (res?.error) {
          window.ChatApp?.setComposerHint(res.error);
        }
      });

      actions.appendChild(btnRename);
      actions.appendChild(btnDel);
      item.appendChild(actions);

      item.addEventListener("click", async () => {
        if (!api() || s.id === activeId) return;
        const res = await api().switch_session(s.id);
        if (res?.ok) {
          activeId = res.active_id || s.id;
          renderSessions(res.sessions);
        } else if (res?.error) {
          window.ChatApp?.setComposerHint(res.error);
        }
      });

      list.appendChild(item);
    });
  }

  function init(state) {
    bindRenameDialog();
    activeId = (state.sessions || []).find((s) => s.active)?.id || "";
    renderSessions(state.sessions || []);
    el("btn-new-session")?.addEventListener("click", async () => {
      if (!api()) return;
      const res = await api().new_session();
      if (res?.ok) {
        activeId = res.active_id || "";
        renderSessions(res.sessions);
        window.ChatUI.clear();
        if (res.events) {
          res.events.forEach((ev) => window.ChatApp.handleEvent(ev));
        }
        const newSession = (res.sessions || []).find((s) => s.id === activeId);
        await openRenameDialog(activeId, newSession?.title || "新会话");
      }
    });
  }

  return { init, renderSessions, openRenameDialog };
})();
