/** 将毫秒耗时格式化为可读短文案，与 legacy ChatUI.formatElapsed 对齐 */
export function formatElapsed(ms: number | null | undefined): string {
  const n = Number(ms);
  if (!Number.isFinite(n) || n < 0) return "";
  if (n < 1000) return `${(n / 1000).toFixed(1)}s`;
  const totalSec = Math.round(n / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return s ? `${m}m${s}s` : `${m}m`;
}
