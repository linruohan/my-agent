/** 聊天区宽度、模型选择与主视图切换 */
window.LayoutUI = (() => {
  let widthSaveTimer = null;
  let layoutPopoverOpen = false;
  let bindingsReady = false;
  let currentView = "chat";

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
    const sel = el("model-select");
    if (!sel) return;
    sel.innerHTML = "";
    const list = Array.isArray(models) && models.length ? models : currentModel ? [currentModel] : [];
    if (!list.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "无可用模型";
      sel.appendChild(opt);
      sel.disabled = true;
      return;
    }
    list.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      if (name === currentModel) opt.selected = true;
      sel.appendChild(opt);
    });
    if (currentModel && !list.includes(currentModel)) {
      const opt = document.createElement("option");
      opt.value = currentModel;
      opt.textContent = currentModel;
      opt.selected = true;
      sel.insertBefore(opt, sel.firstChild);
    }
    sel.disabled = false;
  }

  async function refreshModels(silent = false) {
    const sel = el("model-select");
    if (!sel || !api()) return;
    sel.disabled = true;
    const prev = sel.value;
    try {
      const res = await api().list_provider_models();
      fillModelSelect(res?.models || [], res?.current_model || prev);
      if (res?.error && !silent) {
        window.ChatApp?.setComposerHint?.(`模型列表: ${res.error}`);
      }
    } catch (err) {
      fillModelSelect(prev ? [prev] : [], prev);
      if (!silent) {
        window.ChatApp?.setComposerHint?.(`模型列表加载失败: ${err}`);
      }
    } finally {
      sel.disabled = false;
    }
  }

  function bindModelSelect() {
    const sel = el("model-select");
    sel?.addEventListener("focus", () => {
      refreshModels();
    });
    sel?.addEventListener("change", async (e) => {
      const model = e.target.value;
      if (!model || !api()) return;
      sel.disabled = true;
      try {
        const res = await api().set_model(model);
        if (res?.ok) {
          window.ChatApp?.setStatus?.(res.status_text);
          window.ChatApp?.setComposerHint?.("");
        } else if (res?.error) {
          window.ChatApp?.setComposerHint?.(res.error);
          await refreshModels(true);
        }
      } finally {
        sel.disabled = false;
      }
    });
  }

  function init(state) {
    bindChatWidth();
    bindModelSelect();
    applyChatWidth(state?.chat_width_pct ?? 85);
    const model = state?.composer_meta?.current_model;
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

  return { init, applyChatWidth, refreshModels, fillModelSelect, showView, getCurrentView };
})();
