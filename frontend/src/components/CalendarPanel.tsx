import { useMemo, useState } from "react";
import { Solar } from "lunar-javascript";
import { dateKey, getHolidayType, pad2 } from "@/lib/holidays";
import { dayLabel } from "@/lib/calendar";

const WEEK_LABELS = ["一", "二", "三", "四", "五", "六", "日"];
const WEEK_NAMES = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

type DayCell = {
  y: number;
  m: number;
  d: number;
  outside: boolean;
  col: number;
};

function buildMonthCells(year: number, month: number): DayCell[] {
  const first = new Date(year, month - 1, 1);
  const startOffset = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month, 0).getDate();
  const prevDays = new Date(year, month - 1, 0).getDate();
  const total = Math.ceil((startOffset + daysInMonth) / 7) * 7;
  const cells: DayCell[] = [];

  for (let i = 0; i < total; i++) {
    let y = year;
    let m = month;
    let d: number;
    let outside = false;
    if (i < startOffset) {
      d = prevDays - startOffset + i + 1;
      m = month === 1 ? 12 : month - 1;
      y = month === 1 ? year - 1 : year;
      outside = true;
    } else if (i >= startOffset + daysInMonth) {
      d = i - startOffset - daysInMonth + 1;
      m = month === 12 ? 1 : month + 1;
      y = month === 12 ? year + 1 : year;
      outside = true;
    } else {
      d = i - startOffset + 1;
    }
    cells.push({ y, m, d, outside, col: i % 7 });
  }
  return cells;
}

export function CalendarPanel() {
  const now = new Date();
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth() + 1);
  const [selected, setSelected] = useState({
    y: now.getFullYear(),
    m: now.getMonth() + 1,
    d: now.getDate(),
  });

  const today = {
    y: now.getFullYear(),
    m: now.getMonth() + 1,
    d: now.getDate(),
  };

  const cells = useMemo(
    () => buildMonthCells(viewYear, viewMonth),
    [viewYear, viewMonth],
  );

  const detail = useMemo(() => {
    const solar = Solar.fromYmd(selected.y, selected.m, selected.d);
    const lunar = solar.getLunar();
    const festivals = [
      ...solar.getFestivals(),
      ...lunar.getFestivals(),
      ...lunar.getOtherFestivals(),
    ];
    const holiday = getHolidayType(dateKey(selected.y, selected.m, selected.d));
    const prevJq = lunar.getPrevJieQi();
    const nextJq = lunar.getNextJieQi();
    return {
      lunar,
      festivals,
      holiday,
      yi: (lunar.getDayYi() || []).join("  ") || "—",
      ji: (lunar.getDayJi() || []).join("  ") || "—",
      ganzhi: `${lunar.getYearInGanZhi()}年 ${lunar.getMonthInGanZhi()}月 ${lunar.getDayInGanZhi()}日`,
      prevJq: prevJq
        ? `${prevJq.getName()} ${prevJq.getSolar().getYear()}-${pad2(prevJq.getSolar().getMonth())}-${pad2(prevJq.getSolar().getDay())}`
        : "",
      nextJq: nextJq
        ? `${nextJq.getName()} ${nextJq.getSolar().getYear()}-${pad2(nextJq.getSolar().getMonth())}-${pad2(nextJq.getSolar().getDay())}`
        : "",
      isToday:
        selected.y === today.y && selected.m === today.m && selected.d === today.d,
      weekName: WEEK_NAMES[new Date(selected.y, selected.m - 1, selected.d).getDay()],
    };
  }, [selected, today.y, today.m, today.d]);

  const shiftMonth = (delta: number) => {
    let m = viewMonth + delta;
    let y = viewYear;
    if (m < 1) {
      m = 12;
      y -= 1;
    } else if (m > 12) {
      m = 1;
      y += 1;
    }
    setViewYear(y);
    setViewMonth(m);
  };

  const goToday = () => {
    setViewYear(today.y);
    setViewMonth(today.m);
    setSelected({ ...today });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-app">
      <div className="flex items-center justify-end gap-2 border-b border-border px-6 py-3">
            <button
              type="button"
              onClick={() => shiftMonth(-1)}
              className="rounded-lg border border-border px-2 py-1 text-sm text-fg hover:bg-panel"
            >
              上月
            </button>
            <span className="min-w-[7rem] text-center text-sm font-medium text-fg">
              {viewYear}年{viewMonth}月
            </span>
            <button
              type="button"
              onClick={() => shiftMonth(1)}
              className="rounded-lg border border-border px-2 py-1 text-sm text-fg hover:bg-panel"
            >
              下月
            </button>
            <button
              type="button"
              onClick={goToday}
              className="rounded-lg bg-accent px-2 py-1 text-sm text-accent-fg"
            >
              今天
            </button>
      </div>

      <div className="grid flex-1 gap-6 p-6 lg:grid-cols-[1fr_280px]">
        <div>
          <div className="mb-2 grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground">
            {WEEK_LABELS.map((w) => (
              <div key={w} className="py-1">
                {w}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {cells.map((cell) => {
              const key = dateKey(cell.y, cell.m, cell.d);
              const holiday = getHolidayType(key);
              const isToday =
                cell.y === today.y && cell.m === today.m && cell.d === today.d;
              const isSelected =
                cell.y === selected.y &&
                cell.m === selected.m &&
                cell.d === selected.d;
              const label = dayLabel(cell.y, cell.m, cell.d);
              const weekend = cell.col >= 5;
              return (
                <button
                  key={key + String(cell.outside)}
                  type="button"
                  onClick={() => setSelected({ y: cell.y, m: cell.m, d: cell.d })}
                  className={`relative flex min-h-[64px] flex-col items-center rounded-lg border px-1 py-1.5 text-center transition ${
                    isSelected
                      ? "border-accent bg-accent/10"
                      : "border-transparent hover:bg-panel"
                  } ${cell.outside ? "opacity-40" : ""}`}
                >
                  {holiday ? (
                    <span
                      className={`absolute top-1 right-1 text-[10px] ${
                        holiday === "rest" ? "text-danger" : "text-muted-foreground"
                      }`}
                    >
                      {holiday === "rest" ? "休" : "班"}
                    </span>
                  ) : null}
                  <span
                    className={`text-sm font-medium ${
                      isToday
                        ? "text-accent"
                        : weekend
                          ? "text-danger"
                          : "text-fg"
                    }`}
                  >
                    {cell.d}
                  </span>
                  <span className="mt-0.5 line-clamp-1 text-[10px] text-muted-foreground">
                    {label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <aside className="rounded-[var(--radius-panel)] border border-border bg-panel p-4">
          <div className="text-sm text-muted-foreground">
            {selected.y}年{selected.m}月{selected.d}日 {detail.weekName}
            {detail.isToday ? (
              <span className="ml-2 rounded bg-accent/15 px-1.5 py-0.5 text-xs text-accent">
                今天
              </span>
            ) : null}
            {detail.holiday ? (
              <span
                className={`ml-2 rounded px-1.5 py-0.5 text-xs ${
                  detail.holiday === "rest"
                    ? "bg-danger/15 text-danger"
                    : "bg-border text-muted-foreground"
                }`}
              >
                {detail.holiday === "rest" ? "休" : "班"}
              </span>
            ) : null}
          </div>
          <div className="mt-3 text-5xl font-semibold text-fg">{selected.d}</div>
          <div className="mt-2 text-sm text-muted-foreground">
            （{detail.lunar.getYearShengXiao()}年）农历
            {detail.lunar.getMonthInChinese()}月
            {detail.lunar.getDayInChinese()}
            {detail.festivals.length ? ` ${detail.festivals.join(" ")}` : ""}
          </div>
          <div className="mt-3 text-xs text-muted-foreground">{detail.ganzhi}</div>
          <div className="mt-4 space-y-2 text-sm">
            <div>
              <span className="text-muted-foreground">宜 </span>
              <span className="text-fg">{detail.yi}</span>
            </div>
            <div>
              <span className="text-muted-foreground">忌 </span>
              <span className="text-fg">{detail.ji}</span>
            </div>
          </div>
          <div className="mt-4 space-y-1 text-xs text-muted-foreground">
            {detail.prevJq ? <div>上一节气：{detail.prevJq}</div> : null}
            {detail.nextJq ? <div>下一节气：{detail.nextJq}</div> : null}
          </div>
        </aside>
      </div>
    </div>
  );
}
