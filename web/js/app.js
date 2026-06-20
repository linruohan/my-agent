/** 主应用：pywebview 桥接、主题、设置 */
window.ChatApp = (() => {
  let running = false;
  let providers = {};
  let providerNames = [];
  let appliedThemeKeys = [];

  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function applyTheme(variables) {
    if (!variables) return;
    const root = document.documentElement;
    appliedThemeKeys.forEach((key) => root.style.removeProperty(key));
    appliedThemeKeys = Object.keys(variables);
    Object.entries(variables).forEach(([key, val]) => {
      root.style.setProperty(key, val);
    });
  }

  function setStatus(text) {
    const el = document.getElementById("status-bar");
    if (el) el.textContent = text || "";
  }

  function setRunning(isRunning) {
    running = isRunning;
    const sendBtn = document.getElementById("btn-send");
    const stopBtn = document.getElementById("btn-stop");
    if (sendBtn) sendBtn.disabled = isRunning;
    if (stopBtn) stopBtn.disabled = !isRunning;
  }

  async function sendMessage() {
    if (running || !api()) return;
    const box = document.getElementById("input-box");
    const text = (box.value || "").trim();
    if (!text) return;
    box.value = "";
    try {
      const ok = await api().send_message(text);
      if (ok === false) return;
      setRunning(true);
    } catch (e) {
      console.error(e);
    }
  }

  function bindComposer() {
    const box = document.getElementById("input-box");
    box.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.ctrlKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    document.getElementById("btn-send").addEventListener("click", sendMessage);
    document.getElementById("btn-stop").addEventListener("click", async () => {
      if (api()) await api().stop_agent();
    });
    document.getElementById("btn-new-session").addEventListener("click", async () => {
      if (api()) await api().new_session();
    });
  }

  function fillThemeSelect(catalog, currentId) {
    const sel = document.getElementById("theme-select");
    sel.innerHTML = "";
    (catalog || []).forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      if (t.id === currentId) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function fillProviderSelect(current) {
    const sel = document.getElementById("provider-select");
    sel.innerHTML = "";
    providerNames.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      if (name === current) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function loadProviderFields(name) {
    const p = providers[name];
    if (!p) return;
    document.getElementById("model-input").value = p.model || "";
    document.getElementById("base-url-input").value = p.base_url || "";
    document.getElementById("temp-slider").value = p.temperature ?? 0.7;
    document.getElementById("temp-value").textContent = p.temperature ?? 0.7;
    document.getElementById("api-key-input").value = "";
    const status = document.getElementById("api-key-status");
    if (p.has_api_key) {
      status.textContent = "✓ 已配置 API Key（留空保留，输入新值覆盖）";
      status.className = "hint ok";
    } else {
      status.textContent = "尚未配置 API Key";
      status.className = "hint err";
    }
  }

  function fillFontSelect(catalog, currentId) {
    const sel = document.getElementById("font-select");
    if (!sel) return;
    sel.innerHTML = "";
    (catalog || []).forEach((f) => {
      const opt = document.createElement("option");
      opt.value = f.id;
      opt.textContent = f.name;
      if (f.id === currentId) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  async function openSettings() {
    if (!api()) return;
    const data = await api().get_settings_data();
    providers = data.providers || {};
    providerNames = data.provider_names || [];
    fillThemeSelect(data.theme_catalog, data.theme_id);
    fillFontSelect(data.font_catalog, data.font_id);
    document.getElementById("appearance-select").value = data.appearance || "dark";
    fillProviderSelect(data.current_provider);
    loadProviderFields(data.current_provider);
    document.getElementById("settings-modal").showModal();
  }

  function bindSettings() {
    const modal = document.getElementById("settings-modal");
    document.getElementById("btn-settings").addEventListener("click", openSettings);
    document.getElementById("settings-close").addEventListener("click", () => modal.close());
    document.getElementById("settings-cancel").addEventListener("click", () => modal.close());

    document.getElementById("provider-select").addEventListener("change", (e) => {
      loadProviderFields(e.target.value);
    });

    document.getElementById("temp-slider").addEventListener("input", (e) => {
      document.getElementById("temp-value").textContent = e.target.value;
    });

    document.getElementById("settings-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!api()) return;
      const payload = {
        theme_id: document.getElementById("theme-select").value,
        appearance: document.getElementById("appearance-select").value,
        font_id: document.getElementById("font-select").value,
        provider: document.getElementById("provider-select").value,
        model: document.getElementById("model-input").value,
        base_url: document.getElementById("base-url-input").value,
        api_key: document.getElementById("api-key-input").value,
        temperature: parseFloat(document.getElementById("temp-slider").value),
      };
      const result = await api().save_settings(payload);
      if (result && result.ok) {
        applyTheme(result.theme_variables);
        setStatus(result.status_text);
        modal.close();
      } else if (result && result.error) {
        const status = document.getElementById("api-key-status");
        status.textContent = result.error;
        status.className = "hint err";
      }
    });
  }

  function bindKnowledge() {
    const modal = document.getElementById("knowledge-modal");
    const logEl = document.getElementById("knowledge-log");
    const statsEl = document.getElementById("knowledge-stats");

    async function refreshStats() {
      if (!api()) return;
      const stats = await api().get_knowledge_stats();
      statsEl.textContent = stats.text || "";
    }

    document.getElementById("btn-knowledge").addEventListener("click", async () => {
      logEl.textContent = "";
      await refreshStats();
      modal.showModal();
    });
    document.getElementById("knowledge-close").addEventListener("click", () => modal.close());
    document.getElementById("knowledge-done").addEventListener("click", () => modal.close());

    async function doImport(kind) {
      if (!api()) return;
      logEl.textContent += kind === "files" ? "选择文件…\n" : "选择文件夹…\n";
      const result = await api().import_knowledge(kind);
      if (result.log) logEl.textContent += result.log + "\n";
      if (result.stats_text) statsEl.textContent = result.stats_text;
      logEl.scrollTop = logEl.scrollHeight;
    }

    document.getElementById("knowledge-pick-files").addEventListener("click", () => doImport("files"));
    document.getElementById("knowledge-pick-folder").addEventListener("click", () => doImport("folder"));
  }

  function bindConfirm() {
    const modal = document.getElementById("confirm-modal");
    let pending = false;

    window.showApprovalDialog = (description) => {
      document.getElementById("confirm-description").textContent = description || "确认执行敏感操作？";
      pending = true;
      modal.showModal();
    };

    document.getElementById("confirm-ok").addEventListener("click", async () => {
      modal.close();
      if (pending && api()) {
        pending = false;
        await api().approval_response(true);
      }
    });
    document.getElementById("confirm-cancel").addEventListener("click", async () => {
      modal.close();
      if (pending && api()) {
        pending = false;
        await api().approval_response(false);
      }
    });
  }

  function handleEvent(ev) {
    if (ev.type === "running") {
      setRunning(!!ev.running);
      return;
    }
    if (ev.type === "status") {
      setStatus(ev.text);
      return;
    }
    if (ev.type === "approval") {
      window.showApprovalDialog(ev.description);
      return;
    }
    if (ev.type === "theme") {
      applyTheme(ev.variables);
      return;
    }
    window.ChatUI.handleEvent(ev);
  }

  async function bootstrap() {
    bindComposer();
    bindSettings();
    bindKnowledge();
    bindConfirm();

    if (!api()) return;
    const state = await api().get_initial_state();
    document.title = state.title || document.title;
    applyTheme(state.theme_variables);
    setStatus(state.status_text);
    setRunning(false);
    if (state.welcome) {
      window.ChatUI.handleEvent({ type: "meta", content: "⚙️ " + state.welcome });
    }
  }

  window.addEventListener("pywebviewready", bootstrap);

  return { handleEvent, applyTheme };
})();
