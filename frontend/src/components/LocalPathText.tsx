import {
  createContext,
  useContext,
  useState,
  type ReactNode,
  isValidElement,
  Children,
  cloneElement,
} from "react";
import {
  openLocalPath,
  splitTextByPaths,
  type TextPart,
} from "@/lib/local-path";

export const LocalPathExistsContext = createContext<Record<string, boolean>>({});

function LocalPathChip({ path }: { path: string }) {
  const existsMap = useContext(LocalPathExistsContext);
  const checkKey = path.replace(/:\d+$/, "");
  const known = Object.prototype.hasOwnProperty.call(existsMap, checkKey);
  const exists = known ? existsMap[checkKey] : true;
  const [status, setStatus] = useState<"idle" | "opened" | "error">("idle");
  const [error, setError] = useState("");

  const onOpen = async () => {
    const res = await openLocalPath(path);
    if (!res.ok) {
      setStatus("error");
      setError(res.error || "打开失败");
      window.setTimeout(() => {
        setStatus("idle");
        setError("");
      }, 2000);
      return;
    }
    setStatus("opened");
    window.setTimeout(() => setStatus("idle"), 1500);
  };

  if (known && !exists) {
    return <span className="break-all text-muted">{path}</span>;
  }

  return (
    <span className="local-path inline-flex max-w-full flex-wrap items-center gap-1 align-baseline">
      <button
        type="button"
        onClick={() => void onOpen()}
        title={`打开 ${path}`}
        className="break-all rounded px-0.5 text-left text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
      >
        {path}
      </button>
      <button
        type="button"
        onClick={() => void onOpen()}
        title="用默认应用打开"
        className="shrink-0 rounded border border-border bg-app px-1.5 py-0.5 text-[10px] text-muted hover:text-fg"
      >
        {status === "opened" ? "已打开" : status === "error" ? "失败" : "打开"}
      </button>
      {error ? <span className="text-[10px] text-danger">{error}</span> : null}
    </span>
  );
}

function renderParts(parts: TextPart[], keyPrefix: string): ReactNode[] {
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.type === "path") {
      return <LocalPathChip key={key} path={part.value} />;
    }
    return <span key={key}>{part.value}</span>;
  });
}

/** 将文本节点中的 Windows 绝对路径替换为可点击芯片；跳过已是元素的子树 */
export function enhanceLocalPaths(children: ReactNode): ReactNode {
  return Children.map(children, (child, index) => {
    if (typeof child === "string") {
      const parts = splitTextByPaths(child);
      if (parts.length === 1 && parts[0].type === "text") return child;
      return <>{renderParts(parts, `p${index}`)}</>;
    }
    if (typeof child === "number") return child;
    if (!isValidElement(child)) return child;

    const el = child as React.ReactElement<{ children?: ReactNode }>;
    // 不深入 code / pre / a，避免破坏代码与链接
    const type = el.type;
    if (type === "code" || type === "pre" || type === "a") return child;

    if (el.props?.children == null) return child;
    return cloneElement(el, {
      ...el.props,
      children: enhanceLocalPaths(el.props.children),
    });
  });
}
