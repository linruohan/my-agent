/** 通用确认弹窗，替代 window.confirm */
window.ConfirmUI = (() => {
  let resolveFn = null;

  function finish(result) {
    resolveFn?.(result);
    resolveFn = null;
    document.getElementById("action-confirm-modal")?.close();
  }

  function bind() {
    const modal = document.getElementById("action-confirm-modal");
    const okBtn = document.getElementById("action-confirm-ok");
    const cancelBtn = document.getElementById("action-confirm-cancel");
    if (!modal || !okBtn || !cancelBtn) return;

    okBtn.addEventListener("click", () => finish(true));
    cancelBtn.addEventListener("click", () => finish(false));
    modal.addEventListener("cancel", (e) => {
      e.preventDefault();
      finish(false);
    });
  }

  /**
   * @param {string} message
   * @param {{ title?: string, confirmText?: string, cancelText?: string, danger?: boolean }} [options]
   * @returns {Promise<boolean>}
   */
  function show(message, options = {}) {
    const modal = document.getElementById("action-confirm-modal");
    const titleEl = document.getElementById("action-confirm-title");
    const messageEl = document.getElementById("action-confirm-message");
    const okBtn = document.getElementById("action-confirm-ok");
    const cancelBtn = document.getElementById("action-confirm-cancel");
    if (!modal || !titleEl || !messageEl || !okBtn || !cancelBtn) {
      return Promise.resolve(false);
    }

    titleEl.textContent = options.title || "确认操作";
    messageEl.textContent = message || "";
    okBtn.textContent = options.confirmText || "确认";
    cancelBtn.textContent = options.cancelText || "取消";
    okBtn.classList.toggle("btn-danger", !!options.danger);
    okBtn.classList.toggle("btn-primary", !options.danger);

    return new Promise((resolve) => {
      resolveFn = resolve;
      modal.showModal();
      cancelBtn.focus();
    });
  }

  bind();
  return { show };
})();
