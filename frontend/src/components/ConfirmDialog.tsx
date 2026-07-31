import { useConfirmStore } from "@/stores/confirm-store";
import { cn } from "@/lib/cn";

export function ConfirmDialog() {
  const open = useConfirmStore((s) => s.open);
  const message = useConfirmStore((s) => s.message);
  const title = useConfirmStore((s) => s.title);
  const confirmText = useConfirmStore((s) => s.confirmText);
  const cancelText = useConfirmStore((s) => s.cancelText);
  const danger = useConfirmStore((s) => s.danger);
  const finish = useConfirmStore((s) => s.finish);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-xl border border-surface-border bg-surface shadow-[var(--menu-shadow)]">
        <div className="border-b border-border px-5 py-4">
          <h2 className="text-body font-semibold text-foreground">{title}</h2>
        </div>
        <div className="px-5 py-4">
          <p className="text-body leading-relaxed text-muted-foreground">{message}</p>
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-5 py-4">
          <button
            type="button"
            onClick={() => finish(false)}
            className="h-8 rounded-lg border border-surface-border px-3 text-label text-foreground hover:bg-surface-hover"
          >
            {cancelText}
          </button>
          <button
            type="button"
            autoFocus
            onClick={() => finish(true)}
            className={cn(
              "h-8 rounded-lg px-3 text-label font-medium",
              danger
                ? "bg-destructive text-brand-foreground"
                : "bg-primary text-primary-foreground",
            )}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
