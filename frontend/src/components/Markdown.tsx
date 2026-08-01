import { memo, useEffect, useState, type ReactNode } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { copyText } from "@/lib/clipboard";
import { checkLocalPaths, extractPathsFromText } from "@/lib/local-path";
import {
  enhanceLocalPaths,
  LocalPathExistsContext,
} from "@/components/LocalPathText";

type Props = {
  content: string;
  className?: string;
};

function CopyFlashButton({
  label,
  getText,
  className = "",
}: {
  label: string;
  getText: () => string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const onClick = async () => {
    const ok = await copyText(getText());
    if (!ok) return;
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button type="button" onClick={() => void onClick()} className={className}>
      {copied ? "已复制" : label}
    </button>
  );
}

function extractCodeText(children: ReactNode): string {
  if (!children) return "";
  const child = Array.isArray(children) ? children[0] : children;
  if (
    child &&
    typeof child === "object" &&
    "props" in child &&
    child.props &&
    typeof (child.props as { children?: unknown }).children === "string"
  ) {
    return (child.props as { children: string }).children.replace(/\n$/, "");
  }
  const parts: string[] = [];
  const walk = (node: ReactNode) => {
    if (node == null || typeof node === "boolean") return;
    if (typeof node === "string" || typeof node === "number") {
      parts.push(String(node));
      return;
    }
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    if (typeof node === "object" && "props" in node) {
      walk((node.props as { children?: ReactNode }).children);
    }
  };
  walk(children);
  return parts.join("").replace(/\n$/, "");
}

function CodeBlock({ children }: { children?: ReactNode }) {
  return (
    <div className="md-code-wrap group relative">
      <CopyFlashButton
        label="复制代码"
        getText={() => extractCodeText(children)}
        className="absolute top-2 right-2 z-10 rounded-md border border-border bg-panel/90 px-2 py-1 text-[11px] text-muted-foreground opacity-0 transition group-hover:opacity-100 hover:text-fg"
      />
      <pre className="md-pre">{children}</pre>
    </div>
  );
}

function PathChildren({ children }: { children?: ReactNode }) {
  return <>{enhanceLocalPaths(children)}</>;
}

const components: Components = {
  pre({ children }) {
    return <CodeBlock>{children}</CodeBlock>;
  },
  p({ children, ...props }) {
    return (
      <p {...props}>
        <PathChildren>{children}</PathChildren>
      </p>
    );
  },
  li({ children, ...props }) {
    return (
      <li {...props}>
        <PathChildren>{children}</PathChildren>
      </li>
    );
  },
  td({ children, ...props }) {
    return (
      <td {...props}>
        <PathChildren>{children}</PathChildren>
      </td>
    );
  },
  th({ children, ...props }) {
    return (
      <th {...props}>
        <PathChildren>{children}</PathChildren>
      </th>
    );
  },
  h1({ children, ...props }) {
    return (
      <h1 {...props}>
        <PathChildren>{children}</PathChildren>
      </h1>
    );
  },
  h2({ children, ...props }) {
    return (
      <h2 {...props}>
        <PathChildren>{children}</PathChildren>
      </h2>
    );
  },
  h3({ children, ...props }) {
    return (
      <h3 {...props}>
        <PathChildren>{children}</PathChildren>
      </h3>
    );
  },
  h4({ children, ...props }) {
    return (
      <h4 {...props}>
        <PathChildren>{children}</PathChildren>
      </h4>
    );
  },
  blockquote({ children, ...props }) {
    return (
      <blockquote {...props}>
        <PathChildren>{children}</PathChildren>
      </blockquote>
    );
  },
};

export const Markdown = memo(function Markdown({ content, className = "" }: Props) {
  const [existsMap, setExistsMap] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    const paths = extractPathsFromText(content);
    if (!paths.length) {
      setExistsMap({});
      return;
    }
    void checkLocalPaths(paths).then((map) => {
      if (!cancelled) setExistsMap(map);
    });
    return () => {
      cancelled = true;
    };
  }, [content]);

  return (
    <LocalPathExistsContext.Provider value={existsMap}>
      <div className={`md-body ${className}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={components}
        >
          {content}
        </ReactMarkdown>
      </div>
    </LocalPathExistsContext.Provider>
  );
});
