/** 聊天消息 DOM 渲染 */
window.ChatUI = (() => {
  function scrollEl() {
    return document.getElementById("chat-scroll");
  }

  function welcomeEl() {
    return document.getElementById("chat-welcome");
  }

  function showWelcome() {
    welcomeEl()?.classList.remove("hidden");
  }

  function hideWelcome() {
    welcomeEl()?.classList.add("hidden");
  }

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

  let scrollScheduled = false;

  function scrollBottom() {
    if (scrollScheduled) return;
    scrollScheduled = true;
    requestAnimationFrame(() => {
      scrollScheduled = false;
      const el = scrollEl();
      if (!el) return;
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

  const WIN_ABS_PATH = /[A-Za-z]:[\\/](?:[^\s<>"'`|]+[\\/])*[^\s<>"'`|]+/g;

  function trimPathTail(raw) {
    let s = raw;
    while (s.length > 3 && /[.,;，。:!?\u3001\u3002)\]}>]$/.test(s)) {
      const ext = s.match(/(\.[A-Za-z0-9]{1,8})$/);
      if (ext && s.endsWith(ext[1])) break;
      s = s.slice(0, -1);
    }
    return s;
  }

  function splitTextByPaths(text) {
    const parts = [];
    WIN_ABS_PATH.lastIndex = 0;
    let last = 0;
    let match;
    while ((match = WIN_ABS_PATH.exec(text)) !== null) {
      const raw = match[0];
      const path = trimPathTail(raw);
      if (path.length < 4) continue;
      if (match.index > last) {
        parts.push({ type: "text", value: text.slice(last, match.index) });
      }
      parts.push({ type: "path", value: path });
      last = match.index + raw.length;
    }
    if (!parts.length) return [{ type: "text", value: text }];
    if (last < text.length) parts.push({ type: "text", value: text.slice(last) });
    return parts;
  }

  async function openLocalPath(path, btn) {
    if (!path) return false;
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.open_local_path) {
      window.alert("当前环境不支持打开本地文件");
      return false;
    }
    try {
      const res = await api.open_local_path(path);
      if (!res || !res.ok) {
        window.alert((res && res.error) || "打开失败");
        return false;
      }
      if (btn) {
        const orig = btn.textContent;
        btn.classList.add("opened");
        btn.textContent = "已打开";
        setTimeout(() => {
          btn.classList.remove("opened");
          btn.textContent = orig;
        }, 1500);
      }
      return true;
    } catch {
      window.alert("打开失败");
      return false;
    }
  }

  async function fetchLocalPathExists(paths) {
    const unique = [...new Set((paths || []).filter(Boolean))];
    if (!unique.length) return {};
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.check_local_paths) return {};
    try {
      return (await api.check_local_paths(unique)) || {};
    } catch {
      return {};
    }
  }

  function buildLocalPathSpan(path) {
    const wrap = document.createElement("span");
    wrap.className = "local-path";

    const text = document.createElement("button");
    text.type = "button";
    text.className = "local-path-text";
    text.textContent = path;
    text.title = `打开 ${path}`;
    text.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openLocalPath(path, openBtn);
    });

    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "local-path-open";
    openBtn.textContent = "打开";
    openBtn.title = "用默认应用打开";
    openBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openLocalPath(path, openBtn);
    });

    wrap.appendChild(text);
    wrap.appendChild(openBtn);
    return wrap;
  }

  async function enhanceLocalPaths(bubble) {
    const root = bubble.querySelector(".md-content");
    if (!root) return;

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        if (parent.closest("pre")) return NodeFilter.FILTER_REJECT;
        if (parent.closest(".local-path")) return NodeFilter.FILTER_REJECT;
        if (!node.textContent || !/[A-Za-z]:[\\/]/.test(node.textContent)) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    const pending = [];
    const pathSet = new Set();
    nodes.forEach((node) => {
      const parts = splitTextByPaths(node.textContent || "");
      if (parts.length === 1 && parts[0].type === "text") return;
      parts.forEach((part) => {
        if (part.type === "path") pathSet.add(part.value);
      });
      pending.push({ node, parts });
    });

    const existsMap = await fetchLocalPathExists([...pathSet]);

    pending.forEach(({ node, parts }) => {
      const frag = document.createDocumentFragment();
      parts.forEach((part) => {
        if (part.type === "path") {
          if (existsMap[part.value]) {
            frag.appendChild(buildLocalPathSpan(part.value));
          } else {
            frag.appendChild(document.createTextNode(part.value));
          }
        } else if (part.value) {
          frag.appendChild(document.createTextNode(part.value));
        }
      });
      node.parentNode.replaceChild(frag, node);
    });
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
    void enhanceLocalPaths(bubble);

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
    hideWelcome();
    scrollBottom();
    return bubble;
  }

  function wrapMarkdownTables(bubble) {
    bubble.querySelectorAll(".md-content table").forEach((table) => {
      if (table.parentElement?.classList.contains("md-table-wrap")) return;
      const wrap = document.createElement("div");
      wrap.className = "md-table-wrap";
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
    if (bubble.querySelector(".md-table-wrap")) {
      bubble.classList.add("bubble-has-table");
      bubble.closest(".msg-row")?.classList.add("has-table");
    }
  }

  function renderMarkdown(bubble, text, role) {
    bubble.classList.remove("streaming");
    ensureBubbleLayout(bubble);
    const body = getBubbleBody(bubble);
    body.innerHTML = `<div class="md-content">${marked.parse(text || "")}</div>`;
    bubble.querySelectorAll(".md-content a").forEach((a) => {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    });
    wrapMarkdownTables(bubble);
    enhanceBubble(bubble, text || "");
  }

  const WEATHER_MAX_WIDTH = 620;

  function chatContentWidth() {
    const scroll = scrollEl();
    if (!scroll) return WEATHER_MAX_WIDTH;
    const available = Math.max(360, scroll.clientWidth - 48);
    return Math.min(WEATHER_MAX_WIDTH, available);
  }

  function layoutWeatherBubble(bubble, iframe) {
    const width = chatContentWidth();
    const row = bubble.closest(".msg-row");
    const col = bubble.closest(".msg-col");
    if (row) row.classList.add("weather-reply");
    if (col) {
      col.style.maxWidth = `${width}px`;
      col.style.width = `${width}px`;
    }
    bubble.style.width = "100%";
    if (iframe) {
      iframe.style.width = "100%";
    }
  }

  function readThemeVariables() {
    const root = document.documentElement;
    const vars = {};
    for (let i = 0; i < root.style.length; i += 1) {
      const key = root.style[i];
      if (key.startsWith("--")) {
        vars[key] = root.style.getPropertyValue(key).trim();
      }
    }
    return vars;
  }

  function applyThemeToWeatherIframe(iframe) {
    try {
      const doc = iframe.contentDocument;
      if (!doc) return;
      const vars = readThemeVariables();
      const root = doc.documentElement;
      Object.entries(vars).forEach(([key, val]) => {
        root.style.setProperty(key, val);
      });
      const mode = vars["--theme-mode"] || "dark";
      root.style.colorScheme = mode === "light" ? "light" : "dark";
      root.dataset.themeMode = mode;
    } catch {
      /* iframe 未就绪 */
    }
  }

  function refreshWeatherIframes() {
    document.querySelectorAll(".weather-iframe").forEach((iframe) => {
      applyThemeToWeatherIframe(iframe);
      const bubble = iframe.closest(".bubble");
      if (bubble) resizeWeatherIframe(iframe, bubble);
    });
  }

  function resizeWeatherIframe(iframe, bubble) {
    layoutWeatherBubble(bubble, iframe);
    applyThemeToWeatherIframe(iframe);
    try {
      const doc = iframe.contentDocument;
      const height = doc?.documentElement?.scrollHeight || doc?.body?.scrollHeight || 520;
      iframe.style.height = `${Math.min(Math.max(height + 16, 320), 900)}px`;
    } catch {
      iframe.style.height = "520px";
    }
    scrollBottom();
  }

  function renderHtml(bubble, html) {
    bubble.classList.remove("streaming");
    bubble.classList.add("weather-bubble");
    bubble.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "html-content weather-html";
    const iframe = document.createElement("iframe");
    iframe.className = "weather-iframe";
    iframe.setAttribute("sandbox", "allow-same-origin allow-scripts allow-popups");
    iframe.srcdoc = html || "";
    layoutWeatherBubble(bubble, iframe);
    iframe.addEventListener("load", () => {
      applyThemeToWeatherIframe(iframe);
      resizeWeatherIframe(iframe, bubble);
    });
    wrap.appendChild(iframe);
    bubble.appendChild(wrap);
    scrollBottom();
  }

  function renderAssistantContent(bubble, content, format) {
    if (format === "html") {
      renderHtml(bubble, content || "");
      return;
    }
    renderMarkdown(bubble, content || "", "assistant");
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

  function ensureBubbleLayout(bubble) {
    if (!bubble) return;
    if (!bubble.querySelector(".bubble-hints")) {
      const hints = document.createElement("div");
      hints.className = "bubble-hints";
      bubble.insertBefore(hints, bubble.firstChild);
    }
    if (!bubble.querySelector(".bubble-body")) {
      const body = document.createElement("div");
      body.className = "bubble-body";
      bubble.appendChild(body);
    }
  }

  function appendBubbleHint(bubble, text, accent) {
    if (!text) return;
    ensureBubbleLayout(bubble);
    const hints = bubble.querySelector(".bubble-hints");
    const item = document.createElement("div");
    item.className = "bubble-hint-item" + (accent ? ` accent-${accent}` : "");
    item.textContent = text;
    const live = hints.querySelector(".bubble-hint-live");
    if (live) hints.insertBefore(item, live);
    else hints.appendChild(item);
    scrollBottom();
  }

  function clearLiveHint() {
    assistantNode?.querySelector(".bubble-hint-live")?.remove();
  }

  function addMetaCapsule(text, accent) {
    const wrap = document.createElement("div");
    wrap.className = "meta-capsule selectable" + (accent ? ` accent-${accent}` : "");
    const span = document.createElement("span");
    span.textContent = text;
    wrap.appendChild(span);
    scrollEl().appendChild(wrap);
    hideWelcome();
    scrollBottom();
  }

  function isAgentHint(text) {
    const t = text || "";
    return (
      t.startsWith("🔧") ||
      t.startsWith("📋") ||
      t.startsWith("🔍") ||
      t.includes("调用工具") ||
      t.includes(" 返回:")
    );
  }

  function getBubbleBody(bubble) {
    ensureBubbleLayout(bubble);
    return bubble.querySelector(".bubble-body");
  }

  function addMeta(text, accent) {
    clearLiveHint();
    if (isAgentHint(text)) {
      appendBubbleHint(ensureAssistantBubble(), text, accent);
      return;
    }
    if (assistantNode) {
      appendBubbleHint(assistantNode, text, accent);
      return;
    }
    addMetaCapsule(text, accent);
  }

  function setBubbleStreamText(bubble, text) {
    getBubbleBody(bubble).textContent = text || "";
  }

  function ensureAssistantBubble() {
    if (!assistantNode) {
      assistantNode = createRow("assistant");
      assistantNode.classList.add("streaming");
      ensureBubbleLayout(assistantNode);
    }
    return assistantNode;
  }

  function setToolStatus(text, accent) {
    if (!text) {
      clearLiveHint();
      return;
    }
    const bubble = ensureAssistantBubble();
    ensureBubbleLayout(bubble);
    const hints = bubble.querySelector(".bubble-hints");
    let live = hints.querySelector(".bubble-hint-live");
    if (!live) {
      live = document.createElement("div");
      live.className = "bubble-hint-live bubble-hint-item";
      hints.appendChild(live);
    }
    live.className = "bubble-hint-live bubble-hint-item" + (accent ? ` accent-${accent}` : "");
    live.textContent = text;
    scrollBottom();
  }

  function clearToolStatus() {
    clearLiveHint();
  }

  function clear() {
    clearToolStatus();
    assistantNode = null;
    streamText = "";
    const el = scrollEl();
    if (!el) return;
    el.querySelectorAll(".msg-row, .meta-capsule").forEach((node) => node.remove());
    showWelcome();
  }

  function handleEvent(ev, options = {}) {
    if (!ev || !ev.type) return;
    const skipScroll = options.skipScroll === true;

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
        ensureBubbleLayout(assistantNode);
        setBubbleStreamText(assistantNode, streamText);
        if (!skipScroll) scrollBottom();
        break;
      case "assistant_token":
        if (!assistantNode) {
          streamText = ev.content || "";
          assistantNode = createRow("assistant");
          assistantNode.classList.add("streaming");
          ensureBubbleLayout(assistantNode);
        } else {
          streamText += ev.content || "";
        }
        if (assistantNode) {
          setBubbleStreamText(assistantNode, streamText);
        }
        if (!skipScroll) scrollBottom();
        break;
      case "assistant_end": {
        let replyBubble = assistantNode;
        const format = ev.content_format || "markdown";
        if (replyBubble) {
          renderAssistantContent(replyBubble, ev.content || streamText, format);
        } else if (ev.content) {
          replyBubble = createRow("assistant");
          renderAssistantContent(replyBubble, ev.content, format);
        }
        appendBubbleElapsed(replyBubble, ev.elapsed_ms);
        assistantNode = null;
        streamText = "";
        clearLiveHint();
        if (!skipScroll) scrollBottom();
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

  function loadHistory(events) {
    clear();
    const list = events || [];
    if (!list.length) {
      showWelcome();
      return;
    }
    hideWelcome();
    list.forEach((ev) => handleEvent(ev, { skipScroll: true }));
    scrollBottom();
  }

  return {
    handleEvent,
    loadHistory,
    clear,
    showWelcome,
    hideWelcome,
    scrollBottom,
    copyText,
    refreshWeatherIframes,
  };
})();
