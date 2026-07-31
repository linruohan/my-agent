import { useMemo, useState } from "react";
import { useAppStore } from "@/stores/app-store";
import type { SlashCatalogItem } from "@/bridge/types";

export function SkillsPanel() {
  const slashCatalog = useAppStore((s) => s.slashCatalog);
  const setActiveView = useAppStore((s) => s.setActiveView);
  const setComposerPrefill = useAppStore((s) => s.setComposerPrefill);
  const [query, setQuery] = useState("");

  const { tools, skills } = useMemo(() => {
    const q = query.trim().toLowerCase();
    const match = (item: SlashCatalogItem) => {
      if (!q) return true;
      return (
        (item.name || "").toLowerCase().includes(q) ||
        (item.desc || "").toLowerCase().includes(q) ||
        (item.slash || "").toLowerCase().includes(q)
      );
    };
    return {
      tools: slashCatalog.filter((i) => i.kind === "tool" && match(i)),
      skills: slashCatalog.filter((i) => i.kind === "skill" && match(i)),
    };
  }, [slashCatalog, query]);

  const apply = (item: SlashCatalogItem) => {
    setComposerPrefill(item.slash || `/${item.name}`);
    setActiveView("chat");
  };

  const Section = ({
    title,
    count,
    items,
    empty,
  }: {
    title: string;
    count: number;
    items: SlashCatalogItem[];
    empty: string;
  }) => (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-fg">
        {title}{" "}
        <span className="font-normal text-muted">{count ? `(${count})` : ""}</span>
      </h3>
      {!items.length ? (
        <p className="text-sm text-muted">{empty}</p>
      ) : (
        <div className="space-y-1">
          {items.map((item) => (
            <button
              key={`${item.kind}-${item.name}`}
              type="button"
              onClick={() => apply(item)}
              className="flex w-full items-center gap-3 rounded-lg border border-border bg-panel px-3 py-2 text-left hover:bg-app"
            >
              <span
                className={`rounded px-1.5 py-0.5 font-mono text-xs ${
                  item.kind === "skill"
                    ? "bg-accent/15 text-accent"
                    : "bg-border/60 text-fg"
                }`}
              >
                {item.slash || `/${item.name}`}
              </span>
              <span className="truncate text-sm text-muted">{item.desc || ""}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-app">
      <div className="border-b border-border px-6 py-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索命令…"
          className="w-full max-w-md rounded-lg border border-border bg-input px-3 py-2 text-sm text-fg outline-none focus:border-accent"
        />
      </div>
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-5">
        <Section title="系统工具" count={tools.length} items={tools} empty="暂无匹配的系统工具" />
        <Section title="Skill" count={skills.length} items={skills} empty="暂无匹配的 Skill" />
      </div>
    </div>
  );
}
