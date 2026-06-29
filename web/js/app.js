/** 主应用：pywebview 桥接、主题、设置 */
window.ChatApp = (() => {
  let running = false;
  let providers = {};
  let providerNames = [];
  let appliedThemeKeys = [];
  let lxgwFontInstalled = true;
  let lxgwFontWarned = false;

  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function ensureWebFontLoaded(fontId) {
    const linkId = "webfont-lxgw-css";
    const need = fontId === "lxgw-wenkai-gb";
    const existing = document.getElementById(linkId);
    if (!need) {
      existing?.remove();
      return;
    }
    if (!lxgwFontInstalled) {
      if (!lxgwFontWarned) {
        lxgwFontWarned = true;
        window.ChatUI?.handleEvent?.({
          type: "meta",
          content:
            "⚙️ 霞鹜文楷未安装，当前使用系统字体。请在项目根目录运行 scripts/install-web-fonts.ps1",
        });
      }
      return;
    }
    if (existing) return;
    const link = document.createElement("link");
    link.id = linkId;
    link.rel = "stylesheet";
    link.href = "css/fonts-lxgw.css";
    document.head.appendChild(link);
  }

  function applyTheme(variables) {
    if (!variables) return;
    ensureWebFontLoaded(variables["--ui-font-id"]);
    const root = document.documentElement;
    appliedThemeKeys.forEach((key) => root.style.removeProperty(key));
    appliedThemeKeys = Object.keys(variables);
    Object.entries(variables).forEach(([key, val]) => {
      root.style.setProperty(key, val);
    });
    const mode = variables["--theme-mode"] || "dark";
    root.dataset.themeMode = mode;
    root.style.colorScheme = mode === "light" ? "light" : "dark";
    window.ChatUI?.refreshWeatherIframes?.();
  }

  function parseStatusText(text) {
    const raw = text || "";
    let model = "—";
    let session = "—";
    const modelMatch = raw.match(/模型:\s*([^|]+)/);
    if (modelMatch) {
      const parts = modelMatch[1].trim().split(/\s*\/\s*/);
      model = parts.length > 1 ? parts[parts.length - 1].trim() : modelMatch[1].trim();
    }
    const sessionMatch = raw.match(/会话:\s*(.+)/);
    if (sessionMatch) session = sessionMatch[1].trim();
    return { model, session, raw };
  }

  function updateStatusDisplay(text) {
    const { model, session, raw } = parseStatusText(text);
    const modelEl = document.getElementById("status-model");
    const sessionEl = document.getElementById("status-session");
    const modelSelect = document.getElementById("model-select");
    if (modelEl) modelEl.textContent = model;
    if (sessionEl) sessionEl.textContent = session;
    if (modelSelect && model && model !== "—") {
      const hasOption = Array.from(modelSelect.options).some((o) => o.value === model);
      if (hasOption) modelSelect.value = model;
    }
    const bar = document.getElementById("status-bar");
    if (bar) bar.classList.toggle("hidden", !raw);
  }

  function setStatus(text) {
    updateStatusDisplay(text);
  }

  function setComposerHint(text) {
    const el = document.getElementById("composer-hint");
    if (el) el.textContent = text || "";
  }

  function setRunning(isRunning) {
    running = isRunning;
    const actionBtn = document.getElementById("btn-action");
    if (!actionBtn) return;
    actionBtn.classList.toggle("running", isRunning);
    actionBtn.title = isRunning ? "停止" : "发送";
    actionBtn.querySelector(".icon-send")?.classList.toggle("hidden", isRunning);
    actionBtn.querySelector(".icon-stop")?.classList.toggle("hidden", !isRunning);
    window.Composer?.setRunning?.(isRunning);
  }

  function isRunning() {
    return running;
  }

  function bindShell() {
    document.getElementById("sidebar-toggle")?.addEventListener("click", () => {
      document.getElementById("app")?.classList.toggle("sidebar-collapsed");
    });

    document.getElementById("btn-home")?.addEventListener("click", () => {
      const scroll = document.getElementById("chat-scroll");
      if (scroll) scroll.scrollTo({ top: 0, behavior: "smooth" });
      document.getElementById("input-box")?.focus();
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
    document.getElementById("font-select").value = data.font_id;
    document.getElementById("appearance-select").value = data.appearance || "dark";
    document.getElementById("skill-dirs-input").value = data.skill_dirs || "";
    document.getElementById("task-owner-input").value = data.task_owner_name || "林若寒";
    const voiceInput = document.getElementById("voice-enabled-input");
    if (voiceInput) voiceInput.checked = !!data.voice_enabled;
    const voiceHint = document.getElementById("voice-settings-hint");
    if (voiceHint) {
      if (!data.voice_supported) {
        voiceHint.textContent = "当前平台不支持语音输入（仅 Windows）";
        voiceHint.className = "hint err";
      } else {
        voiceHint.textContent = "开启后，输入框旁显示话筒按钮，点击开始识别";
        voiceHint.className = "hint";
      }
    }
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
        skill_dirs: document.getElementById("skill-dirs-input").value,
        task_owner_name: document.getElementById("task-owner-input").value,
        voice_enabled: document.getElementById("voice-enabled-input")?.checked || false,
      };
      const result = await api().save_settings(payload);
      if (result && result.ok) {
        applyTheme(result.theme_variables);
        setStatus(result.status_text);
        if (result.composer_meta) {
          window.Composer?.updateVoiceMeta?.(result.composer_meta);
        }
        await window.Composer?.refreshSlashCatalog?.();
        await window.SkillsUI?.refresh?.();
        await window.LayoutUI?.refreshModels?.();
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
    bindShell();
    bindSettings();
    bindKnowledge();
    bindConfirm();
    window.CalendarUI?.init();

    if (!api()) return;
    const state = await api().get_initial_state();
    lxgwFontInstalled = state.lxgw_font_installed !== false;
    document.title = state.title || document.title;
    applyTheme(state.theme_variables);
    setStatus(state.status_text);
    setRunning(false);
    window.LayoutUI?.init(state);
    window.SessionUI?.init(state);
    window.SkillsUI?.init(state);
    window.Composer?.init({
      ...state.composer_meta,
      slash_catalog: state.slash_catalog,
      input_history: state.input_history,
    });
    if (state.session_events && state.session_events.length) {
      window.ChatUI.loadHistory(state.session_events);
    } else {
      if (state.welcome) {
        const desc = document.querySelector(".chat-welcome-desc");
        if (desc) desc.textContent = state.welcome;
      }
      window.ChatUI.showWelcome();
    }
  }

  window.addEventListener("pywebviewready", bootstrap);

  return { handleEvent, applyTheme, setRunning, isRunning, setComposerHint, setStatus };
})();
