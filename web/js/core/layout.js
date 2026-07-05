/** 聊天区宽度、模型选择与主视图切换 */
window.LayoutUI = (() => {
  let widthSaveTimer = null;
  let layoutPopoverOpen = false;
  let bindingsReady = false;
  let currentView = "chat";
  let providerConfig = { type: "", base_url: "", model: "" };

  const NAV_BY_VIEW = {
    skills: "btn-skills",
    knowledge: "btn-knowledge",
    calendar: "sidebar-calendar",
    settings: "btn-settings",
  };

  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function normalizeBaseUrl(baseUrl) {
    return (baseUrl || "").replace(/\/+$/, "");
  }

  function buildModelsUrl(type, baseUrl) {
    const root = normalizeBaseUrl(baseUrl);
    if (!root) return "";
    if (type === "ollama") {
      return `${root}/api/tags`;
    }
    if (root.endsWith("/v1")) {
      return `${root}/models`;
    }
    return `${root}/v1/models`;
  }

  function parseModelsResponse(type, payload) {
    if (type === "ollama") {
      const items = payload?.models || [];
      return items.map((item) => item.name).filter(Boolean);
    }
    const items = payload?.data || [];
    return items.map((item) => item.id).filter(Boolean);
  }

  function updateProviderConfig(meta) {
    if (!meta) return;
    providerConfig = {
      type: meta.provider_type || "",
      base_url: meta.provider_base_url || "",
      model: meta.current_model || "",
    };
  }

  function showView(view) {
    currentView = view || "chat";
    document.querySelectorAll(".main-view").forEach((node) => {
      const active = node.dataset.view === currentView;
      node.classList.toggle("hidden", !active);
    });
    document.querySelectorAll(".nav-item").forEach((node) => {
      node.classList.remove("active");
    });
    el("btn-settings")?.classList.remove("active");
    const navId = NAV_BY_VIEW[currentView];
    if (navId) el(navId)?.classList.add("active");
    el("status-bar")?.classList.toggle("hidden", currentView !== "chat");
    if (layoutPopoverOpen) closeLayoutPopover();
  }

  function getCurrentView() {
    return currentView;
  }

  function applyChatWidth(pct) {
    const value = Math.max(50, Math.min(100, Number(pct) || 85));
    document.documentElement.style.setProperty("--chat-width-pct", `${value}%`);
    const output = el("chat-width-value");
    const slider = el("chat-width-slider");
    if (output) output.textContent = `${value}%`;
    if (slider && Number(slider.value) !== value) slider.value = String(value);
  }

  function closeLayoutPopover() {
    layoutPopoverOpen = false;
    el("chat-layout-popover")?.classList.add("hidden");
    el("btn-chat-layout")?.classList.remove("active");
  }

  function openLayoutPopover() {
    layoutPopoverOpen = true;
    el("chat-layout-popover")?.classList.remove("hidden");
    el("btn-chat-layout")?.classList.add("active");
  }

  function toggleLayoutPopover() {
    if (layoutPopoverOpen) closeLayoutPopover();
    else openLayoutPopover();
  }

  function onWidthChange(pct) {
    applyChatWidth(pct);
    scheduleSaveWidth(pct);
  }

  function scheduleSaveWidth(pct) {
    if (widthSaveTimer) clearTimeout(widthSaveTimer);
    widthSaveTimer = setTimeout(async () => {
      widthSaveTimer = null;
      if (!api()?.save_chat_width) return;
      try {
        await api().save_chat_width(pct);
      } catch (err) {
        console.warn("save_chat_width failed:", err);
      }
    }, 280);
  }

  function bindChatWidth() {
    if (bindingsReady) return;
    bindingsReady = true;

    const slider = el("chat-width-slider");
    const popover = el("chat-layout-popover");

    const handleSlider = (e) => {
      e.stopPropagation();
      onWidthChange(Number(e.target.value));
    };

    slider?.addEventListener("input", handleSlider);
    slider?.addEventListener("change", handleSlider);
    slider?.addEventListener("pointerdown", (e) => e.stopPropagation());
    slider?.addEventListener("mousedown", (e) => e.stopPropagation());
    slider?.addEventListener("click", (e) => e.stopPropagation());

    popover?.addEventListener("mousedown", (e) => e.stopPropagation());
    popover?.addEventListener("click", (e) => e.stopPropagation());

    el("btn-chat-layout")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleLayoutPopover();
    });

    document.addEventListener(
      "mousedown",
      (e) => {
        if (!layoutPopoverOpen) return;
        const wrap = document.querySelector(".chat-layout-wrap");
        if (wrap && !wrap.contains(e.target)) closeLayoutPopover();
      },
      true
    );
  }

  function fillModelSelect(models, currentModel) {
    const btn = el("model-select-btn");
    const listEl = el("model-list");
    if (!btn || !listEl) return;

    const list = Array.isArray(models) && models.length ? models : currentModel ? [currentModel] : [];

    btn.textContent = currentModel || "选择模型";
    btn.disabled = !list.length;

    listEl.innerHTML = "";

    if (!list.length) {
      const emptyItem = document.createElement("button");
      emptyItem.className = "model-list-item";
      emptyItem.textContent = "无可用模型";
      emptyItem.disabled = true;
      listEl.appendChild(emptyItem);
      return;
    }

    list.forEach((name) => {
      const item = document.createElement("button");
      item.className = `model-list-item${name === currentModel ? " active" : ""}`;
      item.textContent = name;
      item.addEventListener("click", async () => {
        closeModelDropdown();
        await setModel(name);
      });
      listEl.appendChild(item);
    });
  }

  async function refreshModels(silent = false) {
    const btn = el("model-select-btn");
    const refreshBtn = el("model-refresh-btn");
    if (!btn) return;

    btn.disabled = true;
    if (refreshBtn) refreshBtn.classList.add("loading");

    const prev = btn.textContent;
    const currentModel = providerConfig.model || (prev !== "加载中…" && prev !== "选择模型" ? prev : "");

    async function fetchModelsDirectly() {
      const url = buildModelsUrl(providerConfig.type, providerConfig.base_url);
      if (!url) throw new Error("未配置 API 地址");

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 12000);

      try {
        const response = await fetch(url, {
          signal: controller.signal,
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const payload = await response.json();
        const models = parseModelsResponse(providerConfig.type, payload);
        return models;
      } finally {
        clearTimeout(timeoutId);
      }
    }

    try {
      if (providerConfig.type && providerConfig.base_url) {
        try {
          const models = await fetchModelsDirectly();
          const uniqueModels = [...new Set(models)].sort((a, b) => a.localeCompare(b));
          if (!uniqueModels.includes(currentModel) && currentModel) {
            uniqueModels.unshift(currentModel);
          }
          fillModelSelect(uniqueModels, currentModel);
          return;
        } catch (directErr) {
          console.warn("直接获取模型列表失败，回退到后端代理:", directErr);
        }
      }

      if (!api()) {
        throw new Error("API 不可用");
      }

      const res = await api().list_provider_models();
      updateProviderConfig(res);
      fillModelSelect(res?.models || [], res?.current_model || currentModel);
      if (res?.error && !silent) {
        window.ChatApp?.setComposerHint?.(`模型列表: ${res.error}`);
      }
    } catch (err) {
      fillModelSelect(currentModel ? [currentModel] : [], currentModel);
      if (!silent) {
        window.ChatApp?.setComposerHint?.(`模型列表加载失败: ${err}`);
      }
    } finally {
      btn.disabled = false;
      if (refreshBtn) refreshBtn.classList.remove("loading");
    }
  }

  function bindModelSelect() {
    const btn = el("model-select-btn");
    const dropdown = el("model-dropdown");
    const refreshBtn = el("model-refresh-btn");

    function toggleModelDropdown() {
      if (!dropdown) return;
      dropdown.classList.toggle("hidden");
    }

    function closeModelDropdown() {
      if (!dropdown) return;
      dropdown.classList.add("hidden");
    }

    btn?.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleModelDropdown();
    });

    refreshBtn?.addEventListener("click", (e) => {
      e.stopPropagation();
      refreshModels();
    });

    document.addEventListener("click", (e) => {
      if (dropdown && !dropdown.contains(e.target) && !btn?.contains(e.target)) {
        closeModelDropdown();
      }
    });
  }

  async function setModel(model) {
    const btn = el("model-select-btn");
    if (!model || !api()) return;

    btn.disabled = true;
    try {
      const res = await api().set_model(model);
      if (res?.ok) {
        window.ChatApp?.setStatus?.(res.status_text);
        window.ChatApp?.setComposerHint?.("");
        if (res.composer_meta) {
          updateProviderConfig(res.composer_meta);
        }
      } else if (res?.error) {
        window.ChatApp?.setComposerHint?.(res.error);
        await refreshModels(true);
      }
    } finally {
      btn.disabled = false;
    }
  }

  function init(state) {
    bindChatWidth();
    bindModelSelect();
    applyChatWidth(state?.chat_width_pct ?? 85);
    updateProviderConfig(state?.composer_meta);
    const model = providerConfig.model;
    fillModelSelect(model ? [model] : [], model);
    if (api()) refreshModels(true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      bindChatWidth();
      applyChatWidth(85);
    });
  } else {
    bindChatWidth();
    applyChatWidth(85);
  }

  return { init, applyChatWidth, refreshModels, fillModelSelect, showView, getCurrentView, updateProviderConfig };
})();
