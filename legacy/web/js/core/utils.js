/** 共享工具模块：API 桥接、DOM 操作、性能优化 */
window.Utils = (() => {
  function api() {
    return window.pywebview && window.pywebview.api;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function on(el, event, handler, options = {}) {
    if (!el) return () => {};
    el.addEventListener(event, handler, options);
    return () => el.removeEventListener(event, handler, options);
  }

  function once(el, event, handler, options = {}) {
    if (!el) return () => {};
    const opts = { ...options, once: true };
    el.addEventListener(event, handler, opts);
    return () => el.removeEventListener(event, handler, opts);
  }

  function debounce(func, wait = 200) {
    let timer = null;
    return function (...args) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => func.apply(this, args), wait);
    };
  }

  function throttle(func, limit = 100) {
    let inThrottle = false;
    return function (...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  }

  function raf(func) {
    let scheduled = false;
    return function (...args) {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        func.apply(this, args);
      });
    };
  }

  function safeCall(func, ...args) {
    try {
      return func(...args);
    } catch (err) {
      console.error("[utils] safeCall error:", err);
      return null;
    }
  }

  function asyncSafeCall(func, ...args) {
    return Promise.resolve()
      .then(() => func(...args))
      .catch((err) => {
        console.error("[utils] asyncSafeCall error:", err);
        return null;
      });
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function unescapeHtml(html) {
    const div = document.createElement("div");
    div.innerHTML = html;
    return div.textContent || div.innerText || "";
  }

  function formatTime(date) {
    const d = date instanceof Date ? date : new Date(date);
    const h = String(d.getHours()).padStart(2, "0");
    const m = String(d.getMinutes()).padStart(2, "0");
    return `${h}:${m}`;
  }

  function formatDate(date) {
    const d = date instanceof Date ? date : new Date(date);
    const y = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, "0");
    const da = String(d.getDate()).padStart(2, "0");
    return `${y}-${mo}-${da}`;
  }

  let _lazyObserver = null;
  const _lazyLoaded = new Set();

  function initLazyLoad() {
    if (_lazyObserver) return;
    if (!window.IntersectionObserver) return;

    _lazyObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !_lazyLoaded.has(entry.target)) {
            const img = entry.target;
            const src = img.getAttribute("data-src");
            if (src) {
              img.src = src;
              _lazyLoaded.add(img);
              _lazyObserver.unobserve(img);
            }
          }
        });
      },
      {
        rootMargin: "100px",
        threshold: 0.01,
      }
    );
  }

  function observeImages(container = document) {
    initLazyLoad();
    if (!_lazyObserver) return;

    container.querySelectorAll("img[data-src]").forEach((img) => {
      if (!_lazyLoaded.has(img)) {
        _lazyObserver.observe(img);
      }
    });
  }

  function observeImage(img) {
    initLazyLoad();
    if (!_lazyObserver || _lazyLoaded.has(img)) return;
    _lazyObserver.observe(img);
  }

  function disposeLazyLoad() {
    if (_lazyObserver) {
      _lazyObserver.disconnect();
      _lazyObserver = null;
    }
    _lazyLoaded.clear();
  }

  return {
    api,
    el,
    on,
    once,
    debounce,
    throttle,
    raf,
    safeCall,
    asyncSafeCall,
    escapeHtml,
    unescapeHtml,
    formatTime,
    formatDate,
    initLazyLoad,
    observeImages,
    observeImage,
    disposeLazyLoad,
  };
})();