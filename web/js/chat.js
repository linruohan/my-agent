/** 聊天消息 DOM 渲染 */
window.ChatUI = (() => {
  const scrollEl = () => document.getElementById("chat-scroll");
  const toolStatusEl = () => document.getElementById("tool-status");

  let assistantNode = null;
  let streamText = "";

  marked.setOptions({
    breaks: true,
    gfm: true,
  });

  function nowLabel() {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  function formatElapsed(ms) {
    const n = Number(ms);
    if (!Number.isFinite(n) || n < 0) return "";
    if (n < 1000) return `${(n / 1000).toFixed(1)}s`;
    const totalSec = Math.round(n / 1000);
    if (totalSec < 60) return `${totalSec}s`;
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return s ? `${m}m${s}s` : `${m}m`;
  }

  function appendBubbleElapsed(bubble, elapsedMs) {
    if (!bubble || elapsedMs == null) return;
    const elapsed = formatElapsed(elapsedMs);
    if (!elapsed) return;
    bubble.querySelector(".bubble-elapsed")?.remove();
    const footer = document.createElement("div");
    footer.className = "bubble-elapsed";
    footer.textContent = `耗时 ${elapsed}`;
    bubble.appendChild(footer);
  }

  function scrollBottom() {
    const el = scrollEl();
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
      const last = el.lastElementChild;
      if (last && typeof last.scrollIntoView === "function") {
        last.scrollIntoView({ block: "end", behavior: "auto" });
      }
    });
  }

  async function copyText(text, btn) {
    const value = text || "";
    if (!value) return false;
    let ok = false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(value);
        ok = true;
      }
    } catch {
      ok = false;
    }
    if (!ok && window.pywebview && window.pywebview.api && window.pywebview.api.copy_to_clipboard) {
      try {
        ok = await window.pywebview.api.copy_to_clipboard(value);
      } catch {
        ok = false;
      }
    }
    if (!ok) {
      try {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        ok = document.execCommand("copy");
        document.body.removeChild(ta);
      } catch {
        ok = false;
      }
    }
    if (ok && btn) {
      flashCopied(btn);
    }
    return ok;
  }

  function flashCopied(btn) {
    const orig = btn.textContent;
    btn.classList.add("copied");
    btn.textContent = "已复制";
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.textContent = orig;
    }, 1500);
  }

  function getBubblePlainText(bubble) {
    const md = bubble.querySelector(".md-content");
    return (md ? md.innerText : bubble.innerText).trim();
  }

  function enhanceCodeBlocks(bubble) {
    bubble.querySelectorAll("pre").forEach((pre) => {
      if (pre.closest(".code-block-wrap")) return;

      const codeEl = pre.querySelector("code") || pre;
      const raw = codeEl.textContent || "";
      const langMatch = (codeEl.className || "").match(/language-([\w-]+)/);
      const lang = langMatch ? langMatch[1] : "";

      const wrap = document.createElement("div");
      wrap.className = "code-block-wrap";

      const header = document.createElement("div");
      header.className = "code-block-header";

      if (lang) {
        const langSpan = document.createElement("span");
        langSpan.className = "code-lang";
        langSpan.textContent = lang;
        header.appendChild(langSpan);
      } else {
        header.appendChild(document.createElement("span"));
      }

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "code-copy-btn";
      copyBtn.textContent = "复制代码";
      copyBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        copyText(raw, copyBtn);
      });
      header.appendChild(copyBtn);

      const parent = pre.parentNode;
      parent.insertBefore(wrap, pre);
      wrap.appendChild(header);
      wrap.appendChild(pre);
    });
  }

  function enhanceBubble(bubble, rawMarkdown) {
    bubble.classList.add("selectable");
    if (rawMarkdown) {
      bubble.dataset.rawMarkdown = rawMarkdown;
    }

    enhanceCodeBlocks(bubble);

    if (bubble.querySelector(".bubble-toolbar")) return;

    const toolbar = document.createElement("div");
    toolbar.className = "bubble-toolbar";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "bubble-copy-btn";
    copyBtn.textContent = "复制";
    copyBtn.title = "复制消息正文";
    copyBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      copyText(getBubblePlainText(bubble), copyBtn);
    });
    toolbar.appendChild(copyBtn);

    if (bubble.dataset.rawMarkdown) {
      const mdBtn = document.createElement("button");
      mdBtn.type = "button";
      mdBtn.className = "bubble-copy-btn";
      mdBtn.textContent = "复制 MD";
      mdBtn.title = "复制 Markdown 原文";
      mdBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        copyText(bubble.dataset.rawMarkdown, mdBtn);
      });
      toolbar.appendChild(mdBtn);
    }

    bubble.appendChild(toolbar);
  }

  function createRow(role) {
    const row = document.createElement("div");
    row.className = `msg-row ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "👤" : "🤖";

    const col = document.createElement("div");
    col.className = "msg-col";

    const meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = role === "user" ? `我 · ${nowLabel()}` : `助理 · ${nowLabel()}`;

    const bubble = document.createElement("div");
    bubble.className = `bubble selectable ${role}`;

    col.appendChild(meta);
    col.appendChild(bubble);

    if (role === "user") {
      row.appendChild(col);
      row.appendChild(avatar);
    } else {
      row.appendChild(avatar);
      row.appendChild(col);
    }

    scrollEl().appendChild(row);
    scrollBottom();
    return bubble;
  }

  function renderMarkdown(bubble, text, role) {
    bubble.classList.remove("streaming");
    bubble.innerHTML = `<div class="md-content">${marked.parse(text || "")}</div>`;
    bubble.querySelectorAll("a").forEach((a) => {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    });
    enhanceBubble(bubble, text || "");
  }

  function ensureLightbox() {
    if (document.getElementById("image-lightbox")) return;
    const dlg = document.createElement("dialog");
    dlg.id = "image-lightbox";
    dlg.className = "image-lightbox";
    dlg.innerHTML = `
      <button type="button" class="lightbox-close" aria-label="关闭">✕</button>
      <figure class="lightbox-figure">
        <img id="lightbox-img" alt="" />
        <figcaption id="lightbox-caption"></figcaption>
      </figure>
    `;
    dlg.querySelector(".lightbox-close").addEventListener("click", () => dlg.close());
    dlg.addEventListener("click", (e) => {
      if (e.target === dlg) dlg.close();
    });
    document.body.appendChild(dlg);
  }

  function openImageLightbox(src, caption) {
    ensureLightbox();
    const dlg = document.getElementById("image-lightbox");
    const img = document.getElementById("lightbox-img");
    const cap = document.getElementById("lightbox-caption");
    if (!dlg || !img) return;
    img.src = src;
    img.alt = caption || "图片";
    if (cap) {
      cap.textContent = caption || "";
      cap.classList.toggle("hidden", !caption);
    }
    dlg.showModal();
  }

  function renderUserBubble(bubble, ev) {
    bubble.classList.remove("streaming");
    bubble.innerHTML = "";

    if (ev.images && ev.images.length) {
      const gallery = document.createElement("div");
      gallery.className = "msg-images";
      ev.images.forEach((imgMeta) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "msg-image-btn";
        btn.title = imgMeta.name || "点击查看大图";
        const img = document.createElement("img");
        img.src = imgMeta.data_url;
        img.alt = imgMeta.name || "图片";
        img.className = "msg-image";
        btn.appendChild(img);
        img.addEventListener("load", scrollBottom);
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          openImageLightbox(imgMeta.data_url, imgMeta.name);
        });
        gallery.appendChild(btn);
      });
      bubble.appendChild(gallery);
    }

    if (ev.content) {
      const md = document.createElement("div");
      md.className = "md-content";
      md.innerHTML = marked.parse(ev.content);
      md.querySelectorAll("a").forEach((a) => {
        a.target = "_blank";
        a.rel = "noopener noreferrer";
      });
      bubble.appendChild(md);
    }

    enhanceBubble(bubble, ev.content || "");
  }

  function addMeta(text, accent) {
    clearToolStatus();
    const wrap = document.createElement("div");
    wrap.className = "meta-capsule selectable" + (accent ? ` accent-${accent}` : "");
    const span = document.createElement("span");
    span.textContent = text;
    wrap.appendChild(span);
    scrollEl().appendChild(wrap);
    scrollBottom();
  }

  function setToolStatus(text, accent) {
    const el = toolStatusEl();
    if (!el) return;
    if (!text) {
      clearToolStatus();
      return;
    }
    el.classList.remove("hidden");
    el.textContent = text;
    el.style.color =
      accent === "success"
        ? "var(--success)"
        : accent === "error"
          ? "var(--danger)"
          : accent === "info"
            ? "var(--info)"
            : "var(--meta-fg)";
    scrollBottom();
  }

  function clearToolStatus() {
    const el = toolStatusEl();
    if (el) {
      el.classList.add("hidden");
      el.textContent = "";
    }
  }

  function clear() {
    clearToolStatus();
    assistantNode = null;
    streamText = "";
    const el = scrollEl();
    if (el) el.innerHTML = "";
  }

  function handleEvent(ev) {
    if (!ev || !ev.type) return;

    switch (ev.type) {
      case "clear":
        clear();
        break;
      case "user": {
        const userBubble = createRow("user");
        renderUserBubble(userBubble, ev);
        break;
      }
      case "assistant_start":
        streamText = ev.content || "";
        assistantNode = createRow("assistant");
        assistantNode.classList.add("streaming");
        if (streamText) {
          assistantNode.textContent = streamText;
        } else {
          assistantNode.textContent = "";
        }
        scrollBottom();
        break;
      case "assistant_token":
        if (!assistantNode) {
          streamText = ev.content || "";
          assistantNode = createRow("assistant");
          assistantNode.classList.add("streaming");
        } else {
          streamText += ev.content || "";
        }
        if (assistantNode) {
          assistantNode.textContent = streamText;
        }
        scrollBottom();
        break;
      case "assistant_end": {
        let replyBubble = assistantNode;
        if (replyBubble) {
          renderMarkdown(replyBubble, ev.content || streamText, "assistant");
        } else if (ev.content) {
          replyBubble = createRow("assistant");
          renderMarkdown(replyBubble, ev.content, "assistant");
        }
        appendBubbleElapsed(replyBubble, ev.elapsed_ms);
        assistantNode = null;
        streamText = "";
        clearToolStatus();
        scrollBottom();
        break;
      }
      case "assistant_reset":
        if (assistantNode) {
          const row = assistantNode.closest(".msg-row");
          if (row) row.remove();
        }
        assistantNode = null;
        streamText = "";
        break;
      case "meta":
        addMeta(ev.content, ev.accent);
        break;
      case "tool_status":
        setToolStatus(ev.content, ev.accent);
        break;
      default:
        break;
    }
  }

  return {
    handleEvent,
    clear,
    scrollBottom,
    copyText,
  };
})();
