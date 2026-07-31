import { useMemo } from "react";
import { Solar } from "lunar-javascript";
import { useAppStore } from "@/stores/app-store";
import { dayLabel, lunarLine, todayParts, weekName } from "@/lib/calendar";

type Props = {
  collapsed?: boolean;
};

export function SidebarCalendar({ collapsed = false }: Props) {
  const setActiveView = useAppStore((s) => s.setActiveView);
  const activeView = useAppStore((s) => s.activeView);

  const info = useMemo(() => {
    const { y, m, d } = todayParts();
    const lunarDay = Solar.fromYmd(y, m, d).getLunar().getDayInChinese();
    const label = dayLabel(y, m, d);
    return {
      y,
      m,
      d,
      week: weekName(y, m, d),
      lunar: lunarLine(y, m, d),
      sub: label !== lunarDay ? label : "",
    };
  }, []);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setActiveView("calendar")}
        title={`${info.y}年${info.m}月${info.d}日 ${info.week}`}
        className={`flex w-full flex-col items-center rounded-lg border border-border py-1.5 transition ${
          activeView === "calendar"
            ? "bg-panel text-accent shadow-sm"
            : "bg-panel/40 text-accent hover:bg-panel"
        }`}
      >
        <span className="text-lg font-bold leading-none">{info.d}</span>
        <span className="mt-0.5 text-[9px] text-muted">{info.m}月</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setActiveView("calendar")}
      className={`flex w-full items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition ${
        activeView === "calendar"
          ? "border-accent/40 bg-accent/10 shadow-sm"
          : "border-border bg-panel/60 hover:border-accent/30 hover:bg-panel"
      }`}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-[11px] text-muted">
          {info.y}年{info.m}月{info.d}日 {info.week}
        </div>
        <div className="mt-0.5 truncate text-xs text-fg">{info.lunar}</div>
        {info.sub ? (
          <div className="mt-0.5 truncate text-[11px] text-accent">{info.sub}</div>
        ) : null}
      </div>
      <div className="min-w-9 shrink-0 text-center text-2xl font-bold leading-none tracking-tight text-accent">
        {info.d}
      </div>
    </button>
  );
}
