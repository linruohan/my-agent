import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

type Props = {
  html: string;
  className?: string;
  label?: string;
};

function collectThemeVars(): Record<string, string> {
  const root = document.documentElement;
  const vars: Record<string, string> = {};
  for (let i = 0; i < root.style.length; i += 1) {
    const key = root.style[i];
    if (key.startsWith("--")) {
      vars[key] = root.style.getPropertyValue(key).trim();
    }
  }
  const computed = getComputedStyle(root);
  for (const key of [
    "--app-shell",
    "--page-canvas",
    "--surface",
    "--surface-border",
    "--foreground",
    "--muted-foreground",
    "--brand",
    "--border",
    "--bg-app",
    "--bg-panel",
    "--fg",
    "--fg-muted",
    "--accent",
  ]) {
    if (!vars[key]) {
      const val = computed.getPropertyValue(key).trim();
      if (val) vars[key] = val;
    }
  }
  return vars;
}

function applyThemeToDoc(doc: Document) {
  const vars = collectThemeVars();
  const root = doc.documentElement;
  Object.entries(vars).forEach(([key, val]) => {
    root.style.setProperty(key, val);
  });
  const mode =
    vars["--theme-mode"] ||
    document.documentElement.dataset.themeMode ||
    "light";
  root.dataset.themeMode = mode;
  root.style.colorScheme = mode === "light" ? "light" : "dark";
}

/** 将工具返回的完整 HTML（如天气卡片）渲染为自适应高度的沙箱 iframe。 */
export function HtmlEmbed({ html, className, label = "工具结果" }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(420);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const resize = () => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) return;
        applyThemeToDoc(doc);
        const next =
          doc.documentElement?.scrollHeight ||
          doc.body?.scrollHeight ||
          420;
        setHeight(Math.min(Math.max(next + 12, 280), 900));
      } catch {
        setHeight(420);
      }
    };

    const onLoad = () => {
      resize();
      // 图片/字体加载后可能再撑高
      window.setTimeout(resize, 120);
      window.setTimeout(resize, 480);
    };

    iframe.addEventListener("load", onLoad);
    if (iframe.contentDocument?.readyState === "complete") {
      onLoad();
    }

    const onTheme = () => resize();
    window.addEventListener("resize", onTheme);
    const obs = new MutationObserver(onTheme);
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["style", "data-theme-mode"],
    });

    return () => {
      iframe.removeEventListener("load", onLoad);
      window.removeEventListener("resize", onTheme);
      obs.disconnect();
    };
  }, [html]);

  return (
    <div className={cn("html-embed", className)} data-label={label}>
      <iframe
        ref={iframeRef}
        title={label}
        className="weather-iframe"
        sandbox="allow-same-origin allow-scripts allow-popups"
        srcDoc={html}
        style={{ height }}
      />
    </div>
  );
}

export function looksLikeHtmlDocument(content: string): boolean {
  const head = (content || "").trimStart().slice(0, 400).toLowerCase();
  if (!head) return false;
  if (head.startsWith("<!doctype html") || head.startsWith("<html")) return true;
  if (head.includes("<style") && (head.includes("wx-") || head.includes("</html>"))) {
    return true;
  }
  return (
    head.startsWith("<") &&
    (head.includes("</html>") || head.includes("<body") || head.includes("wx-wrap"))
  );
}
