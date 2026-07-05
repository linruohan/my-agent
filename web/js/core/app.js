/** 主应用：pywebview 桥接、主题、设置 */
window.ChatApp = (() => {
  let running = false;
  let providerList = [];
  let appliedThemeKeys = [];
  const { api, el } = window.Utils;

  function applyTheme(variables) {
    if (!variables) return;
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
    const modelBtn = document.getElementById("model-select-btn");
    if (modelEl) modelEl.textContent = model;
    if (sessionEl) sessionEl.textContent = session;
    if (modelBtn && model && model !== "—") {
      modelBtn.textContent = model;
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

  function setProviderSettingsHint(text) {
    const el = document.getElementById("provider-settings-hint");
    if (!el) return;
    const msg = text || "";
    el.textContent = msg;
    el.classList.toggle("hidden", !msg);
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

  function profileInitial(name) {
    const trimmed = (name || "").trim();
    if (!trimmed) return "A";
    const parts = trimmed.split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return trimmed.slice(0, 1).toUpperCase();
  }

  function updateWorkspaceProfile(workspace) {
    if (!workspace) return;
    const nameEl = document.getElementById("profile-name");
    const subEl = document.getElementById("profile-work-dir");
    const avatarEl = document.getElementById("profile-avatar");
    const owner = workspace.owner_name || "个人助理";
    if (nameEl) nameEl.textContent = owner;
    if (subEl) subEl.textContent = workspace.work_dir_label || "点击选择工作目录";
    if (avatarEl) avatarEl.textContent = profileInitial(owner);
    const btn = document.getElementById("btn-work-dir");
    if (btn && workspace.work_dir) {
      btn.title = `工作目录: ${workspace.work_dir}\n点击更换`;
    } else if (btn) {
      btn.title = "选择工作目录";
    }
  }

  function bindShell() {
    document.getElementById("sidebar-toggle")?.addEventListener("click", () => {
      document.getElementById("app")?.classList.toggle("sidebar-collapsed");
    });
  }

  function bindWorkDir() {
    document.getElementById("btn-work-dir")?.addEventListener("click", async () => {
      if (!api()?.pick_work_dir) return;
      try {
        const res = await api().pick_work_dir();
        if (res?.ok) {
          updateWorkspaceProfile({
            owner_name: document.getElementById("profile-name")?.textContent,
            work_dir: res.work_dir,
            work_dir_label: res.work_dir_label,
          });
          if (res.status_text) setStatus(res.status_text);
        } else if (res?.error && !res?.cancelled) {
          setComposerHint(res.error);
        }
      } catch (err) {
        setComposerHint(`选择目录失败: ${err}`);
      }
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

  function renderProviderTable(list) {
    providerList = list || [];
    const tbody = document.getElementById("provider-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!providerList.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="4" class="hint">暂无提供商，点击「添加提供商」创建</td>';
      tbody.appendChild(tr);
      return;
    }
    providerList.forEach((item) => {
      const tr = document.createElement("tr");
      tr.dataset.providerId = item.id;
      const statusHtml = item.active
        ? '<span class="provider-badge">当前</span>'
        : `<button type="button" class="btn-link provider-activate" data-id="${item.id}">设为当前</button>`;
      const deleteBtn = item.deletable
        ? `<button type="button" class="btn-link danger provider-delete" data-id="${item.id}">删除</button>`
        : `<button type="button" class="btn-link danger provider-delete" data-id="${item.id}">移除</button>`;
      tr.innerHTML = `
        <td>${escapeHtml(item.display_name)}</td>
        <td><span class="provider-model" title="${escapeHtml(item.model)}">${escapeHtml(item.model)}</span></td>
        <td>${statusHtml}</td>
        <td class="col-actions">
          <div class="provider-actions">
            <button type="button" class="btn-link provider-edit" data-id="${item.id}">编辑</button>
            ${deleteBtn}
          </div>
        </td>`;
      tbody.appendChild(tr);
    });
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function findProvider(id) {
    return providerList.find((p) => p.id === id);
  }

  function openProviderModal(provider) {
    const modal = document.getElementById("provider-modal");
    const isNew = !provider;
    document.getElementById("provider-modal-title").textContent = isNew ? "添加提供商" : "编辑提供商";
    document.getElementById("provider-id-input").value = provider?.id || "";
    document.getElementById("provider-display-name").value = provider?.display_name || "";
    document.getElementById("provider-type").value = provider?.type || "openai_compatible";
    document.getElementById("provider-model").value = provider?.model || "";
    document.getElementById("provider-base-url").value = provider?.base_url || "";
    document.getElementById("provider-api-key").value = "";
    const temp = provider?.temperature ?? 0.7;
    document.getElementById("provider-temp-slider").value = temp;
    document.getElementById("provider-temp-value").textContent = temp;
    const typeSel = document.getElementById("provider-type");
    if (typeSel) typeSel.disabled = !!(provider && provider.is_builtin);
    const status = document.getElementById("provider-api-key-status");
    if (provider?.has_api_key) {
      status.textContent = "✓ 已配置 API Key（留空保留，输入新值覆盖）";
      status.className = "hint ok";
    } else {
      status.textContent = isNew ? "请填写 API Key" : "尚未配置 API Key";
      status.className = isNew ? "hint err" : "hint";
    }
    modal?.showModal();
  }

  async function handleProviderSave(e) {
    e.preventDefault();
    if (!api()?.save_provider) return;
    const payload = {
      id: document.getElementById("provider-id-input").value,
      display_name: document.getElementById("provider-display-name").value,
      type: document.getElementById("provider-type").value,
      model: document.getElementById("provider-model").value,
      base_url: document.getElementById("provider-base-url").value,
      api_key: document.getElementById("provider-api-key").value,
      temperature: parseFloat(document.getElementById("provider-temp-slider").value),
    };
    const result = await api().save_provider(payload);
    if (result?.ok) {
      renderProviderTable(result.provider_list);
      if (result.status_text) setStatus(result.status_text);
      if (result.composer_meta) {
        window.Composer?.updateProviderMeta?.(result.composer_meta);
        window.LayoutUI?.updateProviderConfig?.(result.composer_meta);
      }
      await window.LayoutUI?.refreshModels?.();
      document.getElementById("provider-modal")?.close();
    } else if (result?.error) {
      const status = document.getElementById("provider-api-key-status");
      status.textContent = result.error;
      status.className = "hint err";
    }
  }

  async function handleProviderAction(e) {
    const editBtn = e.target.closest(".provider-edit");
    const deleteBtn = e.target.closest(".provider-delete");
    const activateBtn = e.target.closest(".provider-activate");
    if (editBtn) {
      openProviderModal(findProvider(editBtn.dataset.id));
      return;
    }
    if (!api()) return;
    if (activateBtn) {
      setProviderSettingsHint("");
      const result = await api().activate_provider(activateBtn.dataset.id);
      if (result?.ok) {
        renderProviderTable(result.provider_list);
        if (result.status_text) setStatus(result.status_text);
        if (result.composer_meta) {
          window.Composer?.updateProviderMeta?.(result.composer_meta);
          window.LayoutUI?.updateProviderConfig?.(result.composer_meta);
        }
        await window.LayoutUI?.refreshModels?.();
      } else if (result?.error) {
        setProviderSettingsHint(result.error);
      }
      return;
    }
    if (deleteBtn) {
      const item = findProvider(deleteBtn.dataset.id);
      const label = item?.display_name || deleteBtn.dataset.id;
      const ok = await window.ConfirmUI?.show(`确定删除提供商「${label}」？`, {
        title: "删除提供商",
        confirmText: "删除",
        danger: true,
      });
      if (!ok) return;
      const result = await api().delete_provider(deleteBtn.dataset.id);
      if (result?.ok) {
        renderProviderTable(result.provider_list);
        if (result.status_text) setStatus(result.status_text);
        if (result.composer_meta) {
          window.Composer?.updateProviderMeta?.(result.composer_meta);
          window.LayoutUI?.updateProviderConfig?.(result.composer_meta);
        }
        await window.LayoutUI?.refreshModels?.();
      } else if (result?.error) {
        setProviderSettingsHint(result.error);
      }
    }
  }

  async function loadSettingsForm() {
    if (!api()) return;
    const data = await api().get_settings_data();
    fillThemeSelect(data.theme_catalog, data.theme_id);
    fillFontSelect(data.font_catalog, data.font_id);
    document.getElementById("font-select").value = data.font_id;
    document.getElementById("appearance-select").value = data.appearance || "dark";
    document.getElementById("skill-dirs-input").value = data.skill_dirs || "";
    document.getElementById("task-owner-input").value = data.task_owner_name || "林若寒";
    renderProviderTable(data.provider_list || []);
  }

  async function openSettings() {
    setProviderSettingsHint("");
    await loadSettingsForm();
    window.LayoutUI?.showView?.("settings");
  }

  function bindSettings() {
    document.getElementById("btn-settings").addEventListener("click", openSettings);
    document.getElementById("settings-cancel").addEventListener("click", () => {
      window.LayoutUI?.showView?.("chat");
    });

    document.getElementById("provider-add")?.addEventListener("click", () => openProviderModal(null));
    document.getElementById("provider-table-body")?.addEventListener("click", handleProviderAction);
    document.getElementById("provider-form")?.addEventListener("submit", handleProviderSave);
    document.getElementById("provider-modal-cancel")?.addEventListener("click", () => {
      document.getElementById("provider-modal")?.close();
    });
    document.getElementById("provider-temp-slider")?.addEventListener("input", (e) => {
      document.getElementById("provider-temp-value").textContent = e.target.value;
    });

    document.getElementById("settings-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!api()) return;
      const payload = {
        theme_id: document.getElementById("theme-select").value,
        appearance: document.getElementById("appearance-select").value,
        font_id: document.getElementById("font-select").value,
        skill_dirs: document.getElementById("skill-dirs-input").value,
        task_owner_name: document.getElementById("task-owner-input").value,
      };
      const result = await api().save_settings(payload);
      if (result && result.ok) {
        applyTheme(result.theme_variables);
        setStatus(result.status_text);
        if (result.workspace) updateWorkspaceProfile(result.workspace);
        await window.Composer?.refreshSlashCatalog?.();
        await window.SkillsUI?.refresh?.();
        window.LayoutUI?.showView?.("chat");
      } else if (result && result.error) {
        setComposerHint(result.error);
      }
    });
  }

  function bindKnowledge() {
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
      window.LayoutUI?.showView?.("knowledge");
    });

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

  function bindWelcomeChips() {
    document.querySelectorAll(".welcome-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const query = chip.dataset.query;
        if (!query) return;
        const box = document.getElementById("input-box");
        if (box) {
          box.value = query;
          box.focus();
          window.Composer?.send?.();
        }
      });
    });
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
    bindWorkDir();
    bindSettings();
    bindKnowledge();
    bindWelcomeChips();
    bindConfirm();
    window.CalendarUI?.init();

    if (!api()) return;
    const state = await api().get_initial_state();
    document.title = state.title || document.title;
    applyTheme(state.theme_variables);
    updateWorkspaceProfile(state.workspace);
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

  return { handleEvent, applyTheme, setRunning, isRunning, setComposerHint, setStatus, updateWorkspaceProfile };
})();
