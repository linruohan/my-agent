import { getApi } from "@/bridge/api";
import { useAppStore } from "@/stores/app-store";

export function ApprovalDialog() {
  const approval = useAppStore((s) => s.approval);
  const setApproval = useAppStore((s) => s.setApproval);

  if (!approval) return null;

  const respond = async (approved: boolean) => {
    const api = getApi();
    setApproval(null);
    if (api) await api.approval_response(approved);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-[var(--radius-panel)] border border-border bg-panel p-5 shadow-lg">
        <h2 className="text-base font-semibold text-fg">需要确认</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
          {approval}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => void respond(false)}
            className="rounded-lg border border-border px-3 py-2 text-sm text-fg"
          >
            拒绝
          </button>
          <button
            type="button"
            onClick={() => void respond(true)}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-fg"
          >
            批准
          </button>
        </div>
      </div>
    </div>
  );
}
