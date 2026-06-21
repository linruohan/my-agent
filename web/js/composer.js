/** 底部 Pill 输入区：附件、语音、斜杠补全、历史 */
window.Composer = (() => {
  let attachments = [];
  let voiceListening = false;
  let lastVoiceResultKey = "";
  let attachMenuOpen = false;
  let actionRunning = false;
  let slashCatalog = [];
  let inputHistory = [];
  let historyIndex = -1;
  let historyDraft = "";
  let slashItems = [];
  let slashIndex = -1;
  let slashOpen = false;

  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function autoResizeInput() {
    const box = el("input-box");
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, 160)}px`;
  }

  function renderAttachments() {
    const strip = el("attachment-strip");
    if (!strip) return;
    strip.innerHTML = "";
    if (!attachments.length) {
      strip.classList.add("hidden");
      return;
    }
    strip.classList.remove("hidden");
    attachments.forEach((att, idx) => {
      const chip = document.createElement("div");
      chip.className = `attach-chip attach-${att.type}`;
      if (att.type === "image" && att.preview) {
        const img = document.createElement("img");
        img.src = att.preview;
        img.alt = att.name || "image";
        chip.appendChild(img);
      }
      const label = document.createElement("span");
      label.className = "attach-label";
      if (att.type === "link") label.textContent = att.url;
      else if (att.type === "file") label.textContent = att.path || att.name;
      else label.textContent = att.name || "图片";
      chip.appendChild(label);
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "attach-remove";
      rm.textContent = "×";
      rm.addEventListener("click", () => {
        attachments.splice(idx, 1);
        renderAttachments();
      });
      chip.appendChild(rm);
      strip.appendChild(chip);
    });
  }

  function addAttachment(att) {
    attachments.push(att);
    renderAttachments();
  }

  function clearInput() {
    const box = el("input-box");
    if (box) {
      box.value = "";
      autoResizeInput();
    }
    attachments = [];
    renderAttachments();
    historyIndex = -1;
    historyDraft = "";
    closeSlashMenu();
  }

  function getPayload() {
    return {
      text: (el("input-box")?.value || "").trim(),
      attachments: attachments.map(({ type, path, url, name }) => ({ type, path, url, name })),
    };
  }

  function slashFilter(text) {
    const body = text || "";
    if (!body.startsWith("/")) return [];
    const rest = body.slice(1).toLowerCase();
    return slashCatalog.filter((item) => {
      const name = (item.name || "").toLowerCase();
      const desc = (item.desc || "").toLowerCase();
      if (!rest) return true;
      return name.includes(rest) || desc.includes(rest) || `/${name}`.includes("/" + rest);
    });
  }

  function renderSlashMenu(items) {
    const menu = el("slash-menu");
    if (!menu) return;
    slashItems = items;
    slashIndex = items.length ? 0 : -1;
    if (!items.length) {
      menu.classList.add("hidden");
      slashOpen = false;
      menu.innerHTML = "";
      return;
    }
    menu.innerHTML = "";
    items.forEach((item, idx) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "slash-item" + (idx === slashIndex ? " active" : "");
      const cmd = document.createElement("span");
      cmd.className = "slash-cmd " + (item.kind === "skill" ? "slash-skill" : "slash-tool");
      cmd.textContent = item.slash || `/${item.name}`;
      const desc = document.createElement("span");
      desc.className = "slash-desc";
      desc.textContent = item.desc || "";
      row.appendChild(cmd);
      row.appendChild(desc);
      row.addEventListener("click", () => applySlashItem(item));
      menu.appendChild(row);
    });
    menu.classList.remove("hidden");
    slashOpen = true;
  }

  function highlightSlashMenu() {
    const menu = el("slash-menu");
    if (!menu) return;
    menu.querySelectorAll(".slash-item").forEach((node, idx) => {
      node.classList.toggle("active", idx === slashIndex);
    });
  }

  function applySlashItem(item) {
    const box = el("input-box");
    if (!box || !item) return;
    box.value = item.slash || `/${item.name}`;
    closeSlashMenu();
    box.focus();
    autoResizeInput();
  }

  function closeSlashMenu() {
    slashOpen = false;
    slashItems = [];
    slashIndex = -1;
    el("slash-menu")?.classList.add("hidden");
  }

  function isOnFirstLine(box) {
    const pos = box.selectionStart ?? 0;
    return box.value.slice(0, pos).indexOf("\n") === -1;
  }

  function isOnLastLine(box) {
    const pos = box.selectionStart ?? 0;
    return box.value.slice(pos).indexOf("\n") === -1;
  }

  function applyHistoryValue(value) {
    const box = el("input-box");
    if (!box) return;
    box.value = value;
    autoResizeInput();
    closeSlashMenu();
    box.setSelectionRange(box.value.length, box.value.length);
  }

  function onInputChange() {
    autoResizeInput();
    const box = el("input-box");
    if (!box) return;
    const val = box.value;
    if (val.startsWith("/")) {
      renderSlashMenu(slashFilter(val));
    } else {
      closeSlashMenu();
    }
    historyIndex = -1;
    historyDraft = "";
  }

  function historyUp() {
    if (!inputHistory.length) return;
    const box = el("input-box");
    if (!box || !isOnFirstLine(box)) return;
    if (historyIndex === -1) {
      historyDraft = box.value;
    }
    if (historyIndex < inputHistory.length - 1) {
      historyIndex += 1;
      applyHistoryValue(inputHistory[historyIndex]);
    }
  }

  function historyDown() {
    const box = el("input-box");
    if (!box || !isOnLastLine(box)) return;
    if (historyIndex <= 0) {
      historyIndex = -1;
      applyHistoryValue(historyDraft);
      return;
    }
    historyIndex -= 1;
    applyHistoryValue(inputHistory[historyIndex]);
  }

  async function send() {
    if (!api() || !window.ChatApp) return false;
    const payload = getPayload();
    if (!payload.text && !payload.attachments.length) {
      window.ChatApp.setComposerHint("输入不能为空");
      return false;
    }
    try {
      const ok = await api().send_message(payload);
      if (ok === false) {
        window.ChatApp.setComposerHint("请等待当前任务完成");
        return false;
      }
      if (payload.text) {
        inputHistory = [payload.text, ...inputHistory.filter((x) => x !== payload.text)].slice(0, 200);
      }
      clearInput();
      return true;
    } catch (e) {
      console.error(e);
      return false;
    }
  }

  async function toggleAction() {
    if (!api() || !window.ChatApp) return;
    if (actionRunning || window.ChatApp.isRunning()) {
      await api().stop_agent();
      return;
    }
    if (slashOpen && slashItems.length && slashIndex >= 0) {
      applySlashItem(slashItems[slashIndex]);
      await send();
      return;
    }
    await send();
  }

  function setRunning(isRunning) {
    actionRunning = isRunning;
  }

  async function pickImage() {
    if (!api()) return;
    const res = await api().pick_input_image();
    closeAttachMenu();
    for (const path of res.paths || []) {
      let preview;
      try {
        const imgData = await api().read_image_data_url(path);
        if (imgData.ok) preview = imgData.data_url;
      } catch {
        preview = undefined;
      }
      addAttachment({
        type: "image",
        path,
        name: path.split(/[/\\]/).pop(),
        preview,
      });
    }
  }

  async function pickFile() {
    if (!api()) return;
    const res = await api().pick_input_file();
    closeAttachMenu();
    (res.paths || []).forEach((path) => {
      addAttachment({ type: "file", path, name: path.split(/[/\\]/).pop() });
    });
  }

  async function promptLink() {
    closeAttachMenu();
    const url = window.prompt("输入链接 URL（http/https）");
    if (!url || !url.trim()) return;
    addAttachment({ type: "link", url: url.trim() });
  }

  function toggleAttachMenu() {
    const menu = el("attach-menu");
    if (!menu) return;
    attachMenuOpen = !attachMenuOpen;
    menu.classList.toggle("hidden", !attachMenuOpen);
  }

  function closeAttachMenu() {
    attachMenuOpen = false;
    el("attach-menu")?.classList.add("hidden");
  }

  async function handlePaste(e) {
    const items = e.clipboardData?.items;
    if (!items || !api()) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        e.preventDefault();
        const blob = item.getAsFile();
        if (!blob) continue;
        const reader = new FileReader();
        reader.onload = async () => {
          const saved = await api().save_pasted_image(String(reader.result));
          if (saved.ok) {
            addAttachment({
              type: "image",
              path: saved.path,
              name: blob.name || "clipboard.png",
              preview: String(reader.result),
            });
          }
        };
        reader.readAsDataURL(blob);
        return;
      }
    }
  }

  async function handleDrop(e) {
    e.preventDefault();
    el("composer-pill")?.classList.remove("drag-over");
    if (!api()) return;

    const dt = e.dataTransfer;
    if (!dt) return;

    if (dt.files && dt.files.length) {
      for (const file of dt.files) {
        const path = file.path;
        if (path) {
          if (file.type.startsWith("image/")) {
            addAttachment({ type: "image", path, name: file.name });
          } else {
            addAttachment({ type: "file", path, name: file.name });
          }
          continue;
        }
        if (file.type.startsWith("image/")) {
          const reader = new FileReader();
          reader.onload = async () => {
            const saved = await api().save_pasted_image(String(reader.result));
            if (saved.ok) {
              addAttachment({
                type: "image",
                path: saved.path,
                name: file.name,
                preview: String(reader.result),
              });
            }
          };
          reader.readAsDataURL(file);
        }
      }
      return;
    }

    const text = dt.getData("text/plain")?.trim();
    if (text) {
      const box = el("input-box");
      if (box) {
        box.value = box.value ? `${box.value}\n${text}` : text;
        onInputChange();
      }
    }
  }

  function voiceLog(...args) {
    console.debug("[voice]", ...args);
  }

  async function startVoice() {
    voiceLog("click", { voiceListening, hasApi: !!api() });
    if (voiceListening) return;
    if (!api()) {
      window.ChatApp?.setComposerHint("语音 API 未就绪，请稍候重试");
      return;
    }
    voiceListening = true;
    el("btn-voice")?.classList.add("listening");
    window.ChatApp?.setComposerHint("正在启动语音…");
    try {
      const info = await api().get_voice_info();
      if (!info.supported) {
        voiceListening = false;
        el("btn-voice")?.classList.remove("listening");
        window.ChatApp?.setComposerHint(info.error || "当前平台不支持语音输入");
        return;
      }
      const started = await api().start_voice_input();
      if (!started || started.ok === false) {
        voiceListening = false;
        el("btn-voice")?.classList.remove("listening");
        window.ChatApp?.setComposerHint(started?.error || "语音启动失败");
        return;
      }
      window.ChatApp?.setComposerHint("正在聆听…");
    } catch (err) {
      voiceListening = false;
      el("btn-voice")?.classList.remove("listening");
      window.ChatApp?.setComposerHint(`语音启动失败: ${err?.message || err}`);
    }
  }

  function onVoiceResult(result) {
    voiceListening = false;
    el("btn-voice")?.classList.remove("listening");
    if (!result?.ok || !result.text) return;
    const box = el("input-box");
    if (box) {
      box.value = box.value.trimEnd() ? `${box.value.trimEnd()} ${result.text.trim()}` : result.text.trim();
      onInputChange();
      box.focus();
    }
  }

  function bind() {
    const box = el("input-box");
    const pill = el("composer-pill");

    box?.addEventListener("input", onInputChange);
    box?.addEventListener("keydown", (e) => {
      if (slashOpen && slashItems.length) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          slashIndex = Math.min(slashIndex + 1, slashItems.length - 1);
          highlightSlashMenu();
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          slashIndex = Math.max(slashIndex - 1, 0);
          highlightSlashMenu();
          return;
        }
        if (e.key === "Tab" && slashIndex >= 0) {
          e.preventDefault();
          applySlashItem(slashItems[slashIndex]);
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          closeSlashMenu();
          return;
        }
      } else if (e.key === "ArrowUp" && !e.shiftKey) {
        e.preventDefault();
        historyUp();
        return;
      } else if (e.key === "ArrowDown" && !e.shiftKey) {
        e.preventDefault();
        historyDown();
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        toggleAction();
      }
    });
    box?.addEventListener("paste", handlePaste);

    el("btn-attach")?.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleAttachMenu();
    });
    el("attach-pick-image")?.addEventListener("click", pickImage);
    el("attach-pick-file")?.addEventListener("click", pickFile);
    el("attach-add-link")?.addEventListener("click", promptLink);
    el("btn-voice")?.addEventListener("click", startVoice);
    el("btn-action")?.addEventListener("click", toggleAction);

    document.addEventListener("click", () => closeAttachMenu());

    pill?.addEventListener("dragover", (e) => {
      e.preventDefault();
      pill.classList.add("drag-over");
    });
    pill?.addEventListener("dragleave", () => pill.classList.remove("drag-over"));
    pill?.addEventListener("drop", handleDrop);
  }

  async function refreshSlashCatalog() {
    if (!api()) return;
    try {
      slashCatalog = (await api().get_slash_catalog()) || [];
    } catch {
      slashCatalog = [];
    }
  }

  function init(meta) {
    bind();
    if (meta?.slash_catalog) slashCatalog = meta.slash_catalog;
    else refreshSlashCatalog();
    if (meta?.input_history) inputHistory = meta.input_history;
    if (meta) {
      const voiceBtn = el("btn-voice");
      if (voiceBtn && meta.voice_supported === false) {
        voiceBtn.title = "语音输入仅 Windows 可用";
        voiceBtn.classList.add("disabled");
      }
    }
    autoResizeInput();
  }

  return {
    init,
    send,
    toggleAction,
    setRunning,
    clearInput,
    onVoiceResult,
    getPayload,
    refreshSlashCatalog,
  };
})();
