/** 左侧会话列表管理 */
window.SessionUI = (() => {
  let activeId = "";

  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function el(id) {
    return document.getElementById(id);
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
        const title = window.prompt("会话名称", s.title);
        if (!title || !title.trim() || !api()) return;
        const res = await api().rename_session(s.id, title.trim());
        if (res?.ok) renderSessions(res.sessions);
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
      }
    });
  }

  return { init, renderSessions };
})();
