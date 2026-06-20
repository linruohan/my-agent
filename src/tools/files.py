from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.infra.files_config import get_fs_option, get_search_roots
from src.tools.cli_hints import append_fallback_hint, cli_tools_status_text

_TEXT_SUFFIXES = {
    ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".js", ".ts", ".tsx",
    ".jsx", ".html", ".css", ".xml", ".csv", ".log", ".ini", ".toml", ".cfg",
}


@dataclass
class FileHit:
    path: Path
    name: str
    is_dir: bool
    size: int
    modified: str


@dataclass
class GrepHit:
    path: Path
    line_no: int
    line: str
    context_before: list[str]
    context_after: list[str]


class PathNotAllowedError(PermissionError):
    pass


def _exclude_dirs() -> set[str]:
    return set(get_fs_option("exclude_dirs", [".git", "node_modules", "__pycache__"]))


def _resolve_root(root: str) -> Path:
    if not root or root.strip() in (".", ""):
        for candidate in get_search_roots():
            return candidate
        return Path.home()

    p = Path(root.strip()).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    _assert_allowed(p)
    if not p.exists():
        raise FileNotFoundError(f"路径不存在: {p}")
    return p


def _assert_allowed(path: Path) -> None:
    resolved = path.resolve()
    for root in get_search_roots():
        try:
            resolved.relative_to(root.resolve())
            return
        except ValueError:
            continue
    allowed = ", ".join(str(r) for r in get_search_roots())
    raise PathNotAllowedError(f"路径不在允许范围内: {path}\n允许目录: {allowed}")


def _should_skip_dir(name: str) -> bool:
    excludes = _exclude_dirs()
    return name in excludes or any(name.lower() == e.lower().lstrip("$") for e in excludes)


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _match_name(name: str, pattern: str, case_sensitive: bool) -> bool:
    if not pattern or pattern in ("*", "*.*"):
        return True
    flags = 0 if case_sensitive else re.IGNORECASE
    # glob 风格
    if any(c in pattern for c in "*?[]"):
        return fnmatch.fnmatch(name if case_sensitive else name.lower(),
                               pattern if case_sensitive else pattern.lower())
    # 子串
    if case_sensitive:
        return pattern in name
    return pattern.lower() in name.lower()


def _find_with_fd(root: Path, pattern: str, file_type: str, max_results: int) -> list[FileHit] | None:
    fd = shutil.which("fd")
    if not fd or not get_fs_option("prefer_cli", True):
        return None
    cmd = [fd, "--max-results", str(max_results), "--max-depth", str(get_fs_option("max_depth", 12))]
    for ex in _exclude_dirs():
        cmd.extend(["--exclude", ex])
    if file_type == "file":
        cmd.append("--type")
        cmd.append("f")
    elif file_type == "dir":
        cmd.append("--type")
        cmd.append("d")
    if pattern and pattern not in ("*", "*.*"):
        cmd.append(pattern)
    cmd.append(str(root))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        if proc.returncode not in (0, 1):
            logger.warning("fd 失败: {}", proc.stderr)
            return None
        hits: list[FileHit] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            p = Path(line.strip())
            if not p.exists():
                continue
            stat = p.stat()
            hits.append(
                FileHit(
                    path=p,
                    name=p.name,
                    is_dir=p.is_dir(),
                    size=stat.st_size if p.is_file() else 0,
                    modified=_fmt_time(stat.st_mtime),
                )
            )
        return hits
    except Exception as exc:
        logger.warning("fd 不可用: {}", exc)
        return None


def _find_python(
    root: Path,
    pattern: str,
    file_type: str,
    max_results: int,
    case_sensitive: bool,
) -> list[FileHit]:
    hits: list[FileHit] = []
    max_depth = int(get_fs_option("max_depth", 12))
    root_depth = len(root.parts)

    def walk(current: Path, depth: int) -> None:
        if len(hits) >= max_results or depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if len(hits) >= max_results:
                return
            if entry.is_dir():
                if _should_skip_dir(entry.name):
                    continue
                if file_type in ("any", "dir") and _match_name(entry.name, pattern, case_sensitive):
                    try:
                        stat = entry.stat()
                        hits.append(
                            FileHit(
                                path=entry,
                                name=entry.name,
                                is_dir=True,
                                size=0,
                                modified=_fmt_time(stat.st_mtime),
                            )
                        )
                    except OSError:
                        pass
                walk(entry, depth + 1)
            elif entry.is_file() and file_type in ("any", "file"):
                if _match_name(entry.name, pattern, case_sensitive):
                    try:
                        stat = entry.stat()
                        hits.append(
                            FileHit(
                                path=entry,
                                name=entry.name,
                                is_dir=False,
                                size=stat.st_size,
                                modified=_fmt_time(stat.st_mtime),
                            )
                        )
                    except OSError:
                        pass

    walk(root, 0)
    return hits


def find_files_impl(
    pattern: str,
    root: str = "",
    file_type: str = "any",
    max_results: int | None = None,
    case_sensitive: bool = False,
) -> str:
    """按文件名/通配符查找文件或文件夹（类似 fd / Everything）。"""
    max_results = max_results or int(get_fs_option("max_results", 80))
    max_results = min(max_results, 200)
    search_root = _resolve_root(root)

    hits = _find_with_fd(search_root, pattern, file_type, max_results)
    engine = "fd"
    if hits is None:
        hits = _find_python(search_root, pattern, file_type, max_results, case_sensitive)
        engine = "python"

    if not hits:
        msg = f"在 {search_root} 下未找到匹配「{pattern}」的{'文件夹' if file_type == 'dir' else '文件'}。"
        return append_fallback_hint(msg, engine, "fd")

    lines = [
        f"【文件搜索】引擎: {engine} | 根目录: {search_root} | 模式: {pattern} | 共 {len(hits)} 条",
        "",
    ]
    for i, h in enumerate(hits, 1):
        kind = "📁" if h.is_dir else "📄"
        size = f" | {h.size:,} B" if not h.is_dir else ""
        lines.append(f"{i}. {kind} {h.path}")
        lines.append(f"   修改时间: {h.modified}{size}")
    if len(hits) >= max_results:
        lines.append(f"\n（已达上限 {max_results} 条，请缩小范围或更精确的模式）")
    return append_fallback_hint("\n".join(lines), engine, "fd")


def _grep_with_rg(
    root: Path,
    pattern: str,
    glob: str,
    max_results: int,
    context: int,
    case_sensitive: bool,
) -> list[GrepHit] | None:
    rg = shutil.which("rg")
    if not rg or not get_fs_option("prefer_cli", True):
        return None
    cmd = [
        rg, "--line-number", "--no-heading", f"--max-count={max_results}",
        f"--max-depth={get_fs_option('max_depth', 12)}",
        f"--context={context}",
    ]
    if not case_sensitive:
        cmd.append("-i")
    for ex in _exclude_dirs():
        cmd.extend(["--glob", f"!{ex}"])
    if glob and glob != "*":
        cmd.extend(["--glob", glob])
    cmd.extend([pattern, str(root)])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
        if proc.returncode not in (0, 1):
            logger.warning("rg 失败: {}", proc.stderr)
            return None
        return _parse_rg_output(proc.stdout, context)
    except Exception as exc:
        logger.warning("rg 不可用: {}", exc)
        return None


def _parse_rg_output(text: str, context: int) -> list[GrepHit]:
    hits: list[GrepHit] = []
    current_file: Path | None = None
    pending_before: list[str] = []
    for line in text.splitlines():
        if line.startswith("--"):
            pending_before = []
            continue
        if ":" not in line:
            continue
        path_str, rest = line.split(":", 1)
        if rest and rest[0].isdigit():
            parts = rest.split(":", 1)
            if len(parts) == 2 and parts[0].isdigit():
                current_file = Path(path_str)
                line_no = int(parts[0])
                content = parts[1]
                hits.append(
                    GrepHit(
                        path=current_file,
                        line_no=line_no,
                        line=content,
                        context_before=list(pending_before),
                        context_after=[],
                    )
                )
                pending_before = []
                continue
        if current_file and line.strip():
            pending_before.append(line)
            if len(pending_before) > context:
                pending_before.pop(0)
    return hits


def _is_text_candidate(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_SUFFIXES:
        return True
    globs = get_fs_option("grep_globs", ["*.txt", "*.md", "*.py"])
    return any(fnmatch.fnmatch(path.name, g) for g in globs)


def _grep_python(
    root: Path,
    pattern: str,
    glob: str,
    max_results: int,
    context: int,
    case_sensitive: bool,
) -> list[GrepHit]:
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        regex = re.compile(re.escape(pattern), flags)

    hits: list[GrepHit] = []
    max_size = int(get_fs_option("max_file_size_mb", 5)) * 1024 * 1024
    max_depth = int(get_fs_option("max_depth", 12))

    def walk(current: Path, depth: int) -> None:
        if len(hits) >= max_results or depth > max_depth:
            return
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if len(hits) >= max_results:
                return
            if entry.is_dir():
                if not _should_skip_dir(entry.name):
                    walk(entry, depth + 1)
            elif entry.is_file() and _is_text_candidate(entry):
                if glob and glob != "*" and not fnmatch.fnmatch(entry.name, glob):
                    continue
                try:
                    if entry.stat().st_size > max_size:
                        continue
                    lines = entry.read_text(encoding="utf-8", errors="ignore").splitlines()
                except (OSError, UnicodeDecodeError):
                    continue
                for idx, line in enumerate(lines):
                    if regex.search(line):
                        before = lines[max(0, idx - context):idx]
                        after = lines[idx + 1 : idx + 1 + context]
                        hits.append(
                            GrepHit(
                                path=entry,
                                line_no=idx + 1,
                                line=line,
                                context_before=before,
                                context_after=after,
                            )
                        )
                        if len(hits) >= max_results:
                            return

    walk(root, 0)
    return hits


def grep_files_impl(
    pattern: str,
    root: str = "",
    glob: str = "*",
    max_results: int | None = None,
    context_lines: int | None = None,
    case_sensitive: bool = False,
) -> str:
    """在文件内容中搜索文本/正则（类似 ripgrep / grep）。"""
    max_results = max_results or int(get_fs_option("max_results", 80))
    max_results = min(max_results, 100)
    context = context_lines if context_lines is not None else int(get_fs_option("grep_context_lines", 2))
    search_root = _resolve_root(root)

    hits = _grep_with_rg(search_root, pattern, glob, max_results, context, case_sensitive)
    engine = "ripgrep (rg)"
    if hits is None:
        hits = _grep_python(search_root, pattern, glob, max_results, context, case_sensitive)
        engine = "python"

    if not hits:
        msg = f"在 {search_root} 下未找到包含「{pattern}」的内容。"
        return append_fallback_hint(msg, engine, "rg")

    lines = [
        f"【内容搜索】引擎: {engine} | 根目录: {search_root} | 模式: {pattern} | 共 {len(hits)} 处",
        "",
    ]
    for i, h in enumerate(hits, 1):
        lines.append(f"{i}. {h.path}:{h.line_no}")
        for ctx in h.context_before:
            lines.append(f"   | {ctx}")
        lines.append(f"   > {h.line}")
        for ctx in h.context_after:
            lines.append(f"   | {ctx}")
        lines.append("")
    return append_fallback_hint("\n".join(lines), engine, "rg")


def read_local_file_impl(path: str, max_lines: int = 200, offset: int = 1) -> str:
    """读取本地文本文件内容（需在允许目录内）。"""
    p = Path(path.strip()).expanduser().resolve()
    _assert_allowed(p)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    if not p.is_file():
        raise IsADirectoryError(f"是目录而非文件: {p}")

    max_size = int(get_fs_option("max_file_size_mb", 5)) * 1024 * 1024
    if p.stat().st_size > max_size:
        raise ValueError(f"文件过大（>{get_fs_option('max_file_size_mb', 5)}MB），请缩小范围或使用 grep_files")

    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    total = len(lines)
    start = max(0, offset - 1)
    end = min(total, start + max_lines)
    selected = lines[start:end]

    header = f"【文件】{p} | 共 {total} 行 | 显示 {start + 1}-{end}\n"
    body = "\n".join(f"{start + i + 1:5}| {line}" for i, line in enumerate(selected))
    if end < total:
        body += f"\n\n… 还有 {total - end} 行未显示，可用 offset={end + 1} 继续读取"
    return header + body


def list_directory_impl(path: str = "", max_entries: int = 100) -> str:
    """列出目录内容（类似资源管理器浏览）。"""
    if path:
        root = Path(path.strip()).expanduser().resolve()
        _assert_allowed(root)
    else:
        root = get_search_roots()[0]
    if not root.exists():
        raise FileNotFoundError(f"路径不存在: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"不是目录: {root}")

    entries: list[tuple[str, Path]] = []
    try:
        for entry in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if _should_skip_dir(entry.name) and entry.is_dir():
                continue
            entries.append(("📁" if entry.is_dir() else "📄", entry))
            if len(entries) >= max_entries:
                break
    except PermissionError:
        raise PermissionError(f"无权限访问: {root}")

    if not entries:
        return f"目录为空: {root}"

    lines = [f"【目录】{root} | 显示 {len(entries)} 项", ""]
    for icon, entry in entries:
        try:
            stat = entry.stat()
            extra = _fmt_time(stat.st_mtime)
            if entry.is_file():
                extra += f" | {stat.st_size:,} B"
        except OSError:
            extra = ""
        lines.append(f"{icon} {entry.name}  ({extra})")
    return "\n".join(lines)
