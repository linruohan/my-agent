import { Moon, Sun } from "lucide-react";
import { useAppStore, type MainView } from "@/stores/app-store";
import { getApi } from "@/bridge/api";
import { cn } from "@/lib/cn";

const VIEW_TITLE: Record<MainView, string> = {
  chat: "聊天",
  tasks: "Tasks",
  skills: "Skills",
  knowledge: "Knowledge",
  calendar: "Calendar",
};

export function MainHeader() {
  const activeView = useAppStore((s) => s.activeView);
  const sessions = useAppStore((s) => s.sessions);
  const appearance = useAppStore((s) => s.appearance);
  const themeId = useAppStore((s) => s.themeId);
  const fontId = useAppStore((s) => s.fontId);
  const patchFromSettings = useAppStore((s) => s.patchFromSettings);

  const sessionTitle = sessions.find((s) => s.active)?.title?.trim() || "";
  const title =
    activeView === "chat"
      ? sessionTitle || "新对话"
      : VIEW_TITLE[activeView];

  const isLight = appearance === "light";

  const toggleAppearance = async () => {
    const api = getApi();
    if (!api?.save_settings) return;
    const next = isLight ? "dark" : "light";
    try {
      const current = await api.get_settings_data();
      const res = await api.save_settings({
        theme_id: current.theme_id || themeId || "default",
        appearance: next,
        font_id: current.font_id || fontId || "system",
        skill_dirs: current.skill_dirs || "",
        task_owner_name: current.task_owner_name || "",
      });
      if (!res?.ok) return;
      patchFromSettings({
        themeVariables: res.theme_variables,
        statusText: res.status_text,
        workspace: res.workspace,
        modelLabel: res.composer_meta?.current_model,
        themeId: current.theme_id || themeId,
        appearance: next,
        fontId: current.font_id || fontId,
      });
    } catch (err) {
      console.warn("toggle appearance failed:", err);
    }
  };

  return (
    <header className="flex h-9 shrink-0 items-center justify-between gap-2 border-b border-border px-3">
      <h1 className="min-w-0 truncate text-label font-semibold text-foreground">
        {title}
      </h1>
      <button
        type="button"
        onClick={() => void toggleAppearance()}
        className={cn(
          "inline-flex size-7 shrink-0 items-center justify-center rounded-md",
          "text-muted-foreground transition-colors",
          "hover:bg-surface-hover hover:text-foreground",
        )}
        title={isLight ? "切换到暗色" : "切换到亮色"}
        aria-label={isLight ? "切换到暗色" : "切换到亮色"}
      >
        {isLight ? (
          <Moon className="size-3.5" strokeWidth={1.75} />
        ) : (
          <Sun className="size-3.5" strokeWidth={1.75} />
        )}
      </button>
    </header>
  );
}
