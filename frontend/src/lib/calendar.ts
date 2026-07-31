import { Solar } from "lunar-javascript";

const WEEK_NAMES = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

export function weekName(y: number, m: number, d: number): string {
  return WEEK_NAMES[new Date(y, m - 1, d).getDay()] || "";
}

export function dayLabel(y: number, m: number, d: number): string {
  const solar = Solar.fromYmd(y, m, d);
  const lunar = solar.getLunar();
  const jq = lunar.getJieQi();
  if (jq) return jq;
  const festivals = [
    ...solar.getFestivals(),
    ...lunar.getFestivals(),
    ...lunar.getOtherFestivals(),
  ];
  if (festivals.length) return festivals[0];
  if (lunar.getDay() === 1) return `${lunar.getMonthInChinese()}月`;
  return lunar.getDayInChinese();
}

export function lunarLine(y: number, m: number, d: number): string {
  const lunar = Solar.fromYmd(y, m, d).getLunar();
  return `农历${lunar.getMonthInChinese()}月${lunar.getDayInChinese()}`;
}

export function todayParts(): { y: number; m: number; d: number } {
  const now = new Date();
  return {
    y: now.getFullYear(),
    m: now.getMonth() + 1,
    d: now.getDate(),
  };
}
