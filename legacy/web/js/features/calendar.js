/** 万年历 UI：侧栏入口 + 主内容区视图 */
window.CalendarUI = (() => {
  const WEEK_LABELS = ["一", "二", "三", "四", "五", "六", "日"];
  const WEEK_NAMES = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

  let viewYear;
  let viewMonth;
  let selectedYear;
  let selectedMonth;
  let selectedDay;
  let today;

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function dateKey(y, m, d) {
    return `${y}-${pad(m)}-${pad(d)}`;
  }

  function syncToday() {
    const now = new Date();
    today = { y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() };
  }

  function getSolar(y, m, d) {
    return Solar.fromYmd(y, m, d);
  }

  function getLunar(y, m, d) {
    return getSolar(y, m, d).getLunar();
  }

  function getDayLabel(y, m, d) {
    const solar = getSolar(y, m, d);
    const lunar = solar.getLunar();
    const jq = lunar.getJieQi();
    if (jq) return jq;
    const festivals = [...solar.getFestivals(), ...lunar.getFestivals(), ...lunar.getOtherFestivals()];
    if (festivals.length) return festivals[0];
    if (lunar.getDay() === 1) return `${lunar.getMonthInChinese()}月`;
    return lunar.getDayInChinese();
  }

  function getWeekNumber(y, m, d) {
    const date = new Date(y, m - 1, d);
    const target = new Date(date.valueOf());
    const dayNr = (date.getDay() + 6) % 7;
    target.setDate(target.getDate() - dayNr + 3);
    const firstThursday = target.valueOf();
    target.setMonth(0, 1);
    if (target.getDay() !== 4) {
      target.setMonth(0, 1 + ((4 - target.getDay() + 7) % 7));
    }
    return 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
  }

  function isWeekend(colIndex) {
    return colIndex >= 5;
  }

  function renderSidebar() {
    const el = document.getElementById("sidebar-calendar");
    if (!el) return;
    const dateEl = el.querySelector(".sidebar-cal-date");
    const dayNumEl = el.querySelector(".sidebar-cal-day-num");
    const lunarEl = el.querySelector(".sidebar-cal-lunar");
    const subEl = el.querySelector(".sidebar-cal-sub");
    if (!dateEl || !dayNumEl || !lunarEl) return;
    syncToday();
    const lunar = getLunar(today.y, today.m, today.d);
    const weekName = WEEK_NAMES[new Date(today.y, today.m - 1, today.d).getDay()];
    dateEl.textContent = `${today.y}年${today.m}月${today.d}日 ${weekName}`;
    dayNumEl.textContent = today.d;
    lunarEl.textContent = `农历${lunar.getMonthInChinese()}月${lunar.getDayInChinese()}`;
    const sub = getDayLabel(today.y, today.m, today.d);
    if (subEl) subEl.textContent = sub !== lunar.getDayInChinese() ? sub : "";
  }

  function buildMonthGrid() {
    const grid = document.getElementById("cal-grid");
    if (!grid) return;
    grid.innerHTML = "";

    const first = new Date(viewYear, viewMonth - 1, 1);
    const startOffset = (first.getDay() + 6) % 7;
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
    const prevDays = new Date(viewYear, viewMonth - 1, 0).getDate();

    const monthLabel = document.getElementById("cal-month-label");
    if (monthLabel) monthLabel.textContent = `${viewYear}年${viewMonth}月`;

    const totalCells = Math.ceil((startOffset + daysInMonth) / 7) * 7;

    for (let i = 0; i < totalCells; i++) {
      let y = viewYear;
      let m = viewMonth;
      let d;
      let outside = false;

      if (i < startOffset) {
        d = prevDays - startOffset + i + 1;
        m = viewMonth === 1 ? 12 : viewMonth - 1;
        y = viewMonth === 1 ? viewYear - 1 : viewYear;
        outside = true;
      } else if (i >= startOffset + daysInMonth) {
        d = i - startOffset - daysInMonth + 1;
        m = viewMonth === 12 ? 1 : viewMonth + 1;
        y = viewMonth === 12 ? viewYear + 1 : viewYear;
        outside = true;
      } else {
        d = i - startOffset + 1;
      }

      const colIndex = i % 7;
      const key = dateKey(y, m, d);
      const holiday = window.getHolidayType?.(key);
      const isToday = y === today.y && m === today.m && d === today.d;
      const isSelected = y === selectedYear && m === selectedMonth && d === selectedDay;

      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cal-cell";
      if (outside) cell.classList.add("outside");
      if (isWeekend(colIndex)) cell.classList.add("weekend");
      if (isToday) cell.classList.add("today");
      if (isSelected) cell.classList.add("selected");
      if (holiday === "rest") cell.classList.add("holiday-rest");
      if (holiday === "work") cell.classList.add("holiday-work");

      const badge = document.createElement("span");
      badge.className = "cal-badge";
      if (holiday === "rest") {
        badge.textContent = "休";
        badge.classList.add("badge-rest");
      } else if (holiday === "work") {
        badge.textContent = "班";
        badge.classList.add("badge-work");
      }

      const num = document.createElement("span");
      num.className = "cal-num";
      num.textContent = d;

      const sub = document.createElement("span");
      sub.className = "cal-sub";
      const label = getDayLabel(y, m, d);
      sub.textContent = label;
      if (holiday === "rest" || /节|元旦|春节|清明|端午|中秋|国庆|情人|母亲|父亲|儿童|劳动|妇女|植树|愚人|万圣|圣诞|七夕|重阳|腊八|小年|除夕|元宵|中元|下元|护士|教师|警察|建军|建党|国庆|植树/.test(label)) {
        sub.classList.add("festive");
      }

      cell.appendChild(badge);
      cell.appendChild(num);
      cell.appendChild(sub);
      cell.addEventListener("click", () => selectDate(y, m, d));
      grid.appendChild(cell);
    }
  }

  function renderDetail() {
    const y = selectedYear;
    const m = selectedMonth;
    const d = selectedDay;
    const solar = getSolar(y, m, d);
    const lunar = solar.getLunar();
    const dow = new Date(y, m - 1, d).getDay();
    const key = dateKey(y, m, d);
    const holiday = window.getHolidayType?.(key);
    const isToday = y === today.y && m === today.m && d === today.d;

    const headerEl = document.getElementById("cal-detail-header");
    if (headerEl) {
      headerEl.innerHTML = `${y}年${m}月${d}日 ${WEEK_NAMES[dow]}<span class="cal-week-num">（第${getWeekNumber(y, m, d)}周）</span>`;
    }

    const todayTag = document.getElementById("cal-today-tag");
    if (todayTag) todayTag.classList.toggle("hidden", !isToday);

    const bigDay = document.getElementById("cal-big-day");
    if (bigDay) bigDay.textContent = d;

    const lunarEl = document.getElementById("cal-lunar-info");
    if (lunarEl) {
      const festivals = [...solar.getFestivals(), ...lunar.getFestivals(), ...lunar.getOtherFestivals()];
      const festText = festivals.length ? ` ${festivals.join(" ")}` : "";
      const shengxiao = lunar.getYearShengXiao();
      lunarEl.textContent = `（${shengxiao}年）农历${lunar.getMonthInChinese()}月${lunar.getDayInChinese()}${festText}`;
    }

    const ganzhiEl = document.getElementById("cal-ganzhi");
    if (ganzhiEl) {
      ganzhiEl.textContent = `${lunar.getYearInGanZhi()}年 ${lunar.getMonthInGanZhi()}月 ${lunar.getDayInGanZhi()}日`;
    }

    const yiEl = document.getElementById("cal-yi");
    if (yiEl) yiEl.textContent = (lunar.getDayYi() || []).join("  ") || "—";

    const jiEl = document.getElementById("cal-ji");
    if (jiEl) jiEl.textContent = (lunar.getDayJi() || []).join("  ") || "—";

    const prevJq = lunar.getPrevJieQi();
    const nextJq = lunar.getNextJieQi();
    const prevEl = document.getElementById("cal-prev-jieqi");
    const nextEl = document.getElementById("cal-next-jieqi");
    if (prevEl && prevJq) {
      const ps = prevJq.getSolar();
      prevEl.textContent = `上一节气：${prevJq.getName()} ${ps.getYear()}-${pad(ps.getMonth())}-${pad(ps.getDay())} ${pad(ps.getHour())}:${pad(ps.getMinute())}`;
    }
    if (nextEl && nextJq) {
      const ns = nextJq.getSolar();
      nextEl.textContent = `下一节气：${nextJq.getName()} ${ns.getYear()}-${pad(ns.getMonth())}-${pad(ns.getDay())} ${pad(ns.getHour())}:${pad(ns.getMinute())}`;
    }

    const holidayEl = document.getElementById("cal-holiday-tag");
    if (holidayEl) {
      holidayEl.classList.remove("hidden", "tag-rest", "tag-work");
      if (holiday === "rest") {
        holidayEl.textContent = "休";
        holidayEl.classList.add("tag-rest");
      } else if (holiday === "work") {
        holidayEl.textContent = "班";
        holidayEl.classList.add("tag-work");
      } else {
        holidayEl.classList.add("hidden");
      }
    }
  }

  function selectDate(y, m, d) {
    selectedYear = y;
    selectedMonth = m;
    selectedDay = d;
    if (y !== viewYear || m !== viewMonth) {
      viewYear = y;
      viewMonth = m;
    }
    buildMonthGrid();
    renderDetail();
  }

  function shiftMonth(delta) {
    viewMonth += delta;
    if (viewMonth > 12) {
      viewMonth = 1;
      viewYear += 1;
    } else if (viewMonth < 1) {
      viewMonth = 12;
      viewYear -= 1;
    }
    buildMonthGrid();
  }

  function shiftDay(delta) {
    const solar = getSolar(selectedYear, selectedMonth, selectedDay).next(delta);
    selectDate(solar.getYear(), solar.getMonth(), solar.getDay());
  }

  function goToday() {
    syncToday();
    selectDate(today.y, today.m, today.d);
  }

  function render() {
    buildMonthGrid();
    renderDetail();
  }

  function openView() {
    syncToday();
    if (!selectedYear) {
      selectedYear = today.y;
      selectedMonth = today.m;
      selectedDay = today.d;
    }
    viewYear = selectedYear;
    viewMonth = selectedMonth;
    render();
    window.LayoutUI?.showView?.("calendar");
  }

  function bind() {
    document.getElementById("sidebar-calendar")?.addEventListener("click", openView);
    document.getElementById("cal-prev-month")?.addEventListener("click", () => shiftMonth(-1));
    document.getElementById("cal-next-month")?.addEventListener("click", () => shiftMonth(1));
    document.getElementById("cal-prev-day")?.addEventListener("click", () => shiftDay(-1));
    document.getElementById("cal-next-day")?.addEventListener("click", () => shiftDay(1));
    document.getElementById("cal-today-btn")?.addEventListener("click", goToday);
  }

  function init() {
    syncToday();
    selectedYear = today.y;
    selectedMonth = today.m;
    selectedDay = today.d;
    viewYear = today.y;
    viewMonth = today.m;
    renderSidebar();
    bind();
    window.addEventListener("holidays-loaded", () => {
      renderSidebar();
      render();
    });

    const weekHead = document.getElementById("cal-week-head");
    if (weekHead) {
      weekHead.innerHTML = WEEK_LABELS.map((w, i) =>
        `<span class="${i >= 5 ? "weekend" : ""}">${w}</span>`
      ).join("");
    }
  }

  return { init, renderSidebar, openView };
})();
