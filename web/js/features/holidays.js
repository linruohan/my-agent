/** 中国法定节假日：休（放假）/ 班（调休上班）。数据源：web/data/holidays.json */
(function () {
  const FALLBACK = {
    rest: [
      "2026-01-01", "2026-01-02", "2026-01-03",
      "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23",
      "2026-04-04", "2026-04-05", "2026-04-06",
      "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
      "2026-06-19", "2026-06-20", "2026-06-21",
      "2026-09-25", "2026-09-26", "2026-09-27",
      "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07",
    ],
    work: [
      "2026-01-04",
      "2026-02-14", "2026-02-28",
      "2026-05-09",
      "2026-09-20", "2026-10-10",
    ],
  };

  function applyHolidayData(data) {
    const rest = Array.isArray(data?.rest) ? data.rest : FALLBACK.rest;
    const work = Array.isArray(data?.work) ? data.work : FALLBACK.work;
    window.CHINA_HOLIDAYS = {
      rest: new Set(rest),
      work: new Set(work),
    };
    window.dispatchEvent(new CustomEvent("holidays-loaded"));
  }

  applyHolidayData(FALLBACK);

  window.getHolidayType = function getHolidayType(dateKey) {
    if (!window.CHINA_HOLIDAYS) return null;
    if (window.CHINA_HOLIDAYS.rest.has(dateKey)) return "rest";
    if (window.CHINA_HOLIDAYS.work.has(dateKey)) return "work";
    return null;
  };

  window.loadChinaHolidays = async function loadChinaHolidays(url) {
    const src = url || "data/holidays.json";
    try {
      const res = await fetch(src, { cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      applyHolidayData(data);
      return true;
    } catch (err) {
      console.warn("加载 holidays.json 失败，使用内置兜底数据:", err);
      applyHolidayData(FALLBACK);
      return false;
    }
  };

  // 异步覆盖为完整数据文件（含多年份）
  window.loadChinaHolidays();
})();
