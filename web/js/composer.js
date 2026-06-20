/** 底部 Pill 输入区：附件、语音、拖拽、粘贴 */
window.Composer = (() => {
  let attachments = [];
  let voiceListening = false;
  let lastVoiceResultKey = "";
  let attachMenuOpen = false;
  let actionRunning = false;

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
  }

  function getPayload() {
    return {
      text: (el("input-box")?.value || "").trim(),
      attachments: attachments.map(({ type, path, url, name }) => ({ type, path, url, name })),
    };
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
        autoResizeInput();
      }
    }
  }

  function voiceLog(...args) {
    console.debug("[voice]", ...args);
  }

  async function startVoice() {
    voiceLog("click", { voiceListening, hasApi: !!api() });
    if (voiceListening) {
      voiceLog("ignored: already listening");
      return;
    }
    if (!api()) {
      voiceLog("ignored: pywebview api not ready");
      window.ChatApp?.setComposerHint("语音 API 未就绪，请稍候重试");
      return;
    }
    voiceListening = true;
    el("btn-voice")?.classList.add("listening");
    window.ChatApp?.setComposerHint("正在启动语音…");
    try {
      voiceLog("get_voice_info …");
      const info = await api().get_voice_info();
      voiceLog("get_voice_info", info);
      if (!info.supported) {
        voiceListening = false;
        el("btn-voice")?.classList.remove("listening");
        window.ChatApp?.setComposerHint(info.error || "当前平台不支持语音输入");
        return;
      }
      window.ChatApp?.setComposerHint("正在检查本地语音…");
      voiceLog("start_voice_input …");
      const started = await api().start_voice_input();
      voiceLog("start_voice_input", started);
      if (!started || started.ok === false) {
        voiceListening = false;
        el("btn-voice")?.classList.remove("listening");
        if (started?.needs_speech_settings) {
          window.ChatApp?.setComposerHint(started.error || "请先开启系统在线语音识别");
        } else if (started?.error) {
          window.ChatApp?.setComposerHint(started.error);
        }
        return;
      }
      window.ChatApp?.setComposerHint("正在聆听… 本地语音识别（无需在线语音）");
    } catch (err) {
      voiceLog("startVoice error", err);
      voiceListening = false;
      el("btn-voice")?.classList.remove("listening");
      window.ChatApp?.setComposerHint(`语音启动失败: ${err?.message || err}`);
    }
  }

  function onVoiceResult(result) {
    voiceLog("onVoiceResult", result);
    voiceListening = false;
    el("btn-voice")?.classList.remove("listening");
    if (!result) return;
    if (result.ok && result.text) {
      const key = `${result.text}|${result.language || ""}`;
      if (key === lastVoiceResultKey) {
        voiceLog("skip duplicate onVoiceResult");
        return;
      }
      lastVoiceResultKey = key;
      const box = el("input-box");
      if (box) {
        const text = result.text.trim();
        const cur = box.value.trimEnd();
        if (cur.endsWith(text)) {
          voiceLog("skip append: already ends with text");
        } else {
          box.value = cur ? `${cur} ${text}` : text;
        }
        autoResizeInput();
        box.focus();
      }
      const lang = result.language ? ` (${result.language})` : "";
      window.ChatApp?.setComposerHint(`语音识别完成${lang}`);
    } else if (result.ok && result.canceled) {
      window.ChatApp?.setComposerHint("已取消语音输入");
    } else if (result.error) {
      window.ChatApp?.setComposerHint(result.error);
    } else if (result.needs_speech_settings) {
      window.ChatApp?.setComposerHint(result.error || "请先开启系统在线语音识别");
    } else {
      window.ChatApp?.setComposerHint("未识别到语音，请重试");
    }
  }

  function bind() {
    const box = el("input-box");
    const pill = el("composer-pill");

    box?.addEventListener("input", autoResizeInput);
    box?.addEventListener("keydown", (e) => {
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

  function init(meta) {
    bind();
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
  };
})();
