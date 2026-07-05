/** 技能与工具浏览页：按系统工具 / Skill 分组展示 */
window.SkillsUI = (() => {
  let catalog = [];

  const { api, el } = window.Utils;

  function groupCatalog(items, filter) {
    const q = (filter || "").trim().toLowerCase();
    const match = (item) => {
      if (!q) return true;
      const name = (item.name || "").toLowerCase();
      const desc = (item.desc || "").toLowerCase();
      const slash = (item.slash || "").toLowerCase();
      return name.includes(q) || desc.includes(q) || slash.includes(q);
    };
    return {
      tools: items.filter((i) => i.kind === "tool" && match(i)),
      skills: items.filter((i) => i.kind === "skill" && match(i)),
    };
  }

  function renderList(container, items, emptyText) {
    if (!container) return;
    container.innerHTML = "";
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "skills-empty";
      empty.textContent = emptyText;
      container.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "skills-item";
      const cmd = document.createElement("span");
      cmd.className = "skills-item-cmd kind-" + (item.kind === "skill" ? "skill" : "tool");
      cmd.textContent = item.slash || `/${item.name}`;
      const desc = document.createElement("span");
      desc.className = "skills-item-desc";
      desc.textContent = item.desc || "";
      row.appendChild(cmd);
      row.appendChild(desc);
      row.addEventListener("click", () => applyItem(item));
      container.appendChild(row);
    });
  }

  function render(filter) {
    const { tools, skills } = groupCatalog(catalog, filter);
    const toolsList = document.getElementById("skills-tools-list");
    const skillsList = document.getElementById("skills-skills-list");
    const toolsCount = document.getElementById("skills-tools-count");
    const skillsCount = document.getElementById("skills-skills-count");
    if (toolsCount) toolsCount.textContent = tools.length ? `(${tools.length})` : "";
    if (skillsCount) skillsCount.textContent = skills.length ? `(${skills.length})` : "";
    renderList(toolsList, tools, "暂无匹配的系统工具");
    renderList(skillsList, skills, "暂无匹配的 Skill");
  }

  function applyItem(item) {
    const box = document.getElementById("input-box");
    if (box && item) {
      box.value = item.slash || `/${item.name}`;
      box.focus();
      box.dispatchEvent(new Event("input", { bubbles: true }));
    }
    window.LayoutUI?.showView?.("chat");
  }

  async function refresh() {
    if (!api()) return;
    catalog = (await api().get_slash_catalog()) || [];
    const search = document.getElementById("skills-search");
    render(search?.value || "");
  }

  async function open() {
    const search = document.getElementById("skills-search");
    if (search) search.value = "";
    await refresh();
    window.LayoutUI?.showView?.("skills");
    search?.focus();
  }

  function bind() {
    document.getElementById("btn-skills")?.addEventListener("click", open);
    document.getElementById("skills-search")?.addEventListener("input", (e) => {
      render(e.target.value);
    });
  }

  function init(state) {
    if (state?.slash_catalog) catalog = state.slash_catalog;
    bind();
  }

  return { init, refresh, open };
})();
