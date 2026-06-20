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

  function scrollBottom() {
    const el = scrollEl();
    if (el) el.scrollTop = el.scrollHeight;
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
        renderMarkdown(userBubble, ev.content, "user");
        break;
      }
      case "assistant_start":
        streamText = "";
        assistantNode = createRow("assistant");
        assistantNode.classList.add("streaming");
        assistantNode.textContent = "";
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
      case "assistant_end":
        if (assistantNode) {
          renderMarkdown(assistantNode, ev.content || streamText, "assistant");
        } else if (ev.content) {
          const b = createRow("assistant");
          renderMarkdown(b, ev.content, "assistant");
        }
        assistantNode = null;
        streamText = "";
        clearToolStatus();
        scrollBottom();
        break;
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
