import holidaysData from "@/data/holidays.json";

type HolidayType = "rest" | "work" | null;

const rest = new Set((holidaysData as { rest?: string[] }).rest || []);
const work = new Set((holidaysData as { work?: string[] }).work || []);

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function dateKey(y: number, m: number, d: number): string {
  return `${y}-${pad2(m)}-${pad2(d)}`;
}

export function getHolidayType(key: string): HolidayType {
  if (rest.has(key)) return "rest";
  if (work.has(key)) return "work";
  return null;
}
