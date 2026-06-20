"""按 SKILL.md 说明直接执行 Skill 脚本（通用，不绑定特定 Skill）。"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from src.ui.skill_catalog import resolve_skill
from src.ui.skill_intent import parse_skill_command_with_llm


@dataclass
class SkillRunResult:
    ok: bool
    output: str = ""
    command: str = ""
    error: str = ""
    fallback_agent: bool = False
    intent_reason: str = ""


@dataclass
class CliParam:
    name: str
    short: str | None = None
    required: bool = False
    positional: bool = False


@dataclass
class CliSpec:
    params: list[CliParam] = field(default_factory=list)


_PATH_RE = re.compile(
    r'"([^"]+)"|\'([^\']+)\'|([A-Za-z]:\\(?:[^"\s]+(?:\\[^"\s]+)*))'
)
_QUOTED_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_NL_VERB_PREFIX = re.compile(r"^(?:获取|提取|导出|处理|运行|执行)\s*", re.I)
_NL_SUFFIX = re.compile(r"(?:的)?(?:表格|表|数据)$", re.I)
_CONTENT_HINT_RE = re.compile(
    r"内容是\s*[\"']?([^\"'\s]+)[\"']?|内容\s+[\"']?([^\"'\s]+)[\"']?",
    re.I,
)
_DESKTOP_HINT_RE = re.compile(r"桌面|desktop", re.I)
_CREATE_DOCX_HINT_RE = re.compile(r"新建.*docx|创建.*docx|生成.*docx", re.I)
_FLAG_PAIR_RE = re.compile(
    r'(--[\w-]+|-\w)\s+("(?:[^"\\]|\\.)*"|\'.+?\'|[^\s-][^\s]*)',
    re.I,
)
_TABLE_ROW_RE = re.compile(
    r"^\|\s*`?([^|`]+?)`?\s*\|\s*`?([^|`]*?)`?\s*\|\s*([^|`]*?)\s*\|",
    re.M,
)
_BASH_BLOCK_RE = re.compile(r"```(?:bash|sh|shell|console)\s*(.*?)```", re.S | re.I)


def _find_entry_script(skill_root: Path, skill_text: str) -> Path | None:
    scripts_dir = skill_root / "scripts"
    if not scripts_dir.is_dir():
        return None

    mentioned: list[str] = []
    for m in re.finditer(r"scripts[/\\]([\w.-]+\.py)", skill_text, re.I):
        name = m.group(1)
        if "test" in name.lower():
            continue
        mentioned.append(name)

    for name in mentioned:
        cand = scripts_dir / name
        if cand.is_file():
            return cand

    priority = [
        f"{skill_root.name.replace('-', '_')}.py",
        "main.py",
        f"{skill_root.name}.py",
    ]
    for name in priority:
        cand = scripts_dir / name
        if cand.is_file():
            return cand

    for py in sorted(scripts_dir.glob("*.py")):
        if py.name.startswith("test") or py.name.startswith("_"):
            continue
        try:
            body = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if 'if __name__ == "__main__"' in body and "argparse" in body:
            return py

    py_files = [p for p in scripts_dir.glob("*.py") if not p.name.startswith("test")]
    return py_files[0] if py_files else None


def _is_required_mark(raw: str) -> bool:
    text = (raw or "").strip().lower()
    return text in {"是", "yes", "true", "必填", "required", "y"}


def _parse_cli_spec_from_skill(skill_text: str, script_name: str) -> CliSpec | None:
    """从 SKILL.md 参数表与 bash 示例解析 CLI 结构。"""
    params: list[CliParam] = []
    seen: set[str] = set()

    for m in _TABLE_ROW_RE.finditer(skill_text):
        name = m.group(1).strip()
        short_raw = m.group(2).strip()
        req_raw = m.group(3).strip()
        if name in {"参数", "------", "-"} or set(name) <= {"-", " "}:
            continue
        if name.startswith("参数") or name.startswith("---"):
            continue

        short = short_raw if short_raw and short_raw != "-" else None
        required = _is_required_mark(req_raw)
        key = name if name.startswith("--") else f"pos:{name}"
        if key in seen:
            continue
        seen.add(key)

        if name.startswith("--"):
            params.append(CliParam(name=name, short=short, required=required, positional=False))
        else:
            params.append(CliParam(name=name, required=required, positional=True))

    if params:
        return CliSpec(params=params)

    for block in _BASH_BLOCK_RE.findall(skill_text):
        if script_name not in block:
            continue
        for line in block.splitlines():
            if script_name not in line:
                continue
            tail = line.split(script_name, 1)[-1].strip()
            if not tail:
                continue
            for token in re.findall(r"<([^>]+)>", tail):
                pname = re.sub(r"\s+", "_", token.strip())
                if f"pos:{pname}" not in seen:
                    seen.add(f"pos:{pname}")
                    params.append(CliParam(name=pname, required=True, positional=True))
            for flag in re.findall(r"--[\w-]+", tail):
                if flag not in seen:
                    seen.add(flag)
                    required = f"[{flag}" not in tail and f"({flag}" not in tail
                    params.append(CliParam(name=flag, required=required, positional=False))
            if params:
                return CliSpec(params=params)

    return None


def _fetch_cli_spec_from_help(entry: Path) -> CliSpec | None:
    """通过脚本 --help 补充 CLI 结构（SKILL.md 未声明时）。"""
    try:
        proc = subprocess.run(
            [sys.executable, str(entry), "--help"],
            cwd=str(entry.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None

    help_text = proc.stdout or ""
    params: list[CliParam] = []
    positional_names = re.findall(r"^\s{2,}([a-zA-Z_][\w-]*)\s+", help_text, re.M)
    for name in positional_names[:3]:
        if name not in {"optional", "positional"}:
            params.append(CliParam(name=name, required=True, positional=True))

    for m in re.finditer(
        r"^\s{2,}(-[\w-]+(?:,\s*)?(?:--[\w-]+)?)\s+(.+)$",
        help_text,
        re.M,
    ):
        opt = m.group(1)
        desc = m.group(2)
        long_flag = re.search(r"--[\w-]+", opt)
        short_flag = re.search(r"(?<![\w-])-[\w](?![\w-])", opt)
        if not long_flag:
            continue
        params.append(
            CliParam(
                name=long_flag.group(0),
                short=short_flag.group(0) if short_flag else None,
                required="required" in desc.lower(),
                positional=False,
            )
        )
    return CliSpec(params=params) if params else None


def _resolve_cli_spec(skill_text: str, entry: Path) -> CliSpec | None:
    spec = _parse_cli_spec_from_skill(skill_text, entry.name)
    if spec and spec.params:
        return spec
    return _fetch_cli_spec_from_help(entry)


def _extract_paths(text: str) -> list[str]:
    paths: list[str] = []
    for m in _PATH_RE.finditer(text or ""):
        p = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if p and p not in paths:
            paths.append(p)
    return paths


def _extract_quoted(text: str) -> list[str]:
    values: list[str] = []
    for m in _QUOTED_RE.finditer(text or ""):
        val = (m.group(1) or m.group(2) or "").strip()
        if val and val not in values:
            values.append(val)
    return values


def _clean_natural_value(raw: str) -> str:
    value = (raw or "").strip().strip("\"'`")
    value = _NL_VERB_PREFIX.sub("", value).strip()
    value = _NL_SUFFIX.sub("", value).strip()
    return value


def _extract_explicit_flags(user_args: str) -> tuple[dict[str, str], str]:
    flags: dict[str, str] = {}
    rest = user_args or ""
    for m in list(_FLAG_PAIR_RE.finditer(rest)):
        key = m.group(1)
        raw_val = m.group(2).strip()
        try:
            val = shlex.split(raw_val)[0]
        except ValueError:
            val = raw_val.strip("\"'")
        flags[key] = val
        rest = rest.replace(m.group(0), " ", 1)
    return flags, rest


def _looks_like_raw_cli(user_args: str) -> bool:
    text = (user_args or "").strip()
    if not text:
        return False
    if text.startswith("-"):
        return True
    return bool(re.search(r"(?:^|\s)-(?:-[\w-]+|\w)(?:\s|$)", text))


def _collect_free_values(remainder: str, paths: list[str], quoted: list[str]) -> list[str]:
    path_keys = set()
    for p in paths:
        try:
            path_keys.add(str(Path(p).resolve()).lower())
        except OSError:
            path_keys.add(p.lower())

    text = remainder or ""
    for p in paths:
        text = text.replace(f'"{p}"', " ")
        text = text.replace(f"'{p}'", " ")
        text = text.replace(p, " ")

    values: list[str] = []
    for q in quoted:
        try:
            if str(Path(q).resolve()).lower() in path_keys:
                continue
        except OSError:
            if q.lower() in path_keys:
                continue
        if q not in values:
            values.append(q)

    for q in quoted:
        text = text.replace(f'"{q}"', " ", 1)
        text = text.replace(f"'{q}'", " ", 1)

    cleaned = _clean_natural_value(text)
    if cleaned and cleaned not in values:
        values.append(cleaned)
    return values


def _parse_natural_hints(user_args: str) -> dict[str, str]:
    """从自然语言中提取通用占位信息（路径、正文等）。"""
    text = user_args or ""
    hints: dict[str, str] = {}

    m = _CONTENT_HINT_RE.search(text)
    if m:
        hints["text"] = (m.group(1) or m.group(2) or "").strip()

    if _DESKTOP_HINT_RE.search(text):
        hints["desktop"] = "1"
        desktop = Path.home() / "Desktop"
        if not desktop.is_dir():
            alt = Path.home() / "桌面"
            if alt.is_dir():
                desktop = alt
        hints["desktop_dir"] = str(desktop)

    if _CREATE_DOCX_HINT_RE.search(text):
        hints["create_docx"] = "1"

    docx_match = re.search(r"([\w.-]+\.docx)", text, re.I)
    if docx_match:
        hints["output_name"] = docx_match.group(1)

    return hints


def _guess_param_value(param: CliParam, hints: dict[str, str], paths: list[str]) -> str | None:
    """根据参数名与自然语言 hints 推断参数值。"""
    names = {param.name.lower(), (param.short or "").lower()}
    norm = param.name.lower().lstrip("-")

    if norm in {"output", "o", "out", "save", "path"} or "output" in names:
        for p in paths:
            if p.lower().endswith(".docx"):
                return p
        if hints.get("desktop_dir"):
            filename = hints.get("output_name")
            if not filename and hints.get("text"):
                safe = re.sub(r'[\\/:*?"<>|]', "_", hints["text"])[:40]
                filename = f"{safe}.docx" if safe else "document.docx"
            filename = filename or "document.docx"
            return str(Path(hints["desktop_dir"]) / filename)
        return paths[0] if paths else None

    if norm in {"text", "t", "content", "body"} or "text" in names:
        return hints.get("text")

    return None


def _find_inline_python_template(skill_text: str) -> str | None:
    """从 SKILL.md bash 块中提取 python -c 模板。"""
    for block in _BASH_BLOCK_RE.findall(skill_text):
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("python") or "-c" not in line:
                continue
            m = re.search(r'-c\s+("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', line)
            if m:
                try:
                    return shlex.split(f"python -c {m.group(1)}")[2]
                except ValueError:
                    raw = m.group(1).strip("\"'")
                    if raw:
                        return raw
    return None


def _fill_inline_template(template: str, values: dict[str, str]) -> str | None:
    keys = set(re.findall(r"\{(\w+)\}", template))
    if not keys:
        return template
    missing = [k for k in keys if k not in values or not values[k]]
    if missing:
        return None
    filled = template
    for key, val in values.items():
        filled = filled.replace("{" + key + "}", val.replace("\\", "\\\\").replace("'", "\\'"))
    return filled


def _build_inline_values(user_args: str, spec: CliSpec | None) -> dict[str, str]:
    hints = _parse_natural_hints(user_args)
    paths = _extract_paths(user_args)
    explicit_flags, remainder = _extract_explicit_flags(user_args)
    quoted = _extract_quoted(remainder)
    free_values = _collect_free_values(remainder, paths, quoted)
    values: dict[str, str] = {}

    if spec:
        idx = 0
        for param in spec.params:
            key = param.name.strip("{}")
            if param.positional:
                val = paths.pop(0) if paths else (free_values[idx] if idx < len(free_values) else None)
                if val:
                    values[key] = val
                    idx += 1
                continue
            flag = param.name
            short = param.short or ""
            val = explicit_flags.get(flag) or explicit_flags.get(short)
            if val is None:
                val = _guess_param_value(param, hints, paths)
            if val is None and param.required and idx < len(free_values):
                val = free_values[idx]
                idx += 1
            if val is not None:
                values[key] = val

    for alias, val in (
        ("text", hints.get("text")),
        ("content", hints.get("text")),
        ("output", _guess_param_value(CliParam(name="--output", required=True), hints, paths)),
    ):
        if val and alias not in values:
            values[alias] = val
    return values


def _normalize_flag_key(flag: str, spec: CliSpec) -> str | None:
    for param in spec.params:
        if not param.positional and (param.name == flag or param.short == flag):
            return param.name
    return flag if flag.startswith("--") else None


def _build_argv(entry: Path, user_args: str, skill_text: str, skill_root: Path) -> list[str] | None:
    """根据 SKILL.md CLI 说明与用户参数构造 argv（不含 python 与脚本路径）。"""
    del skill_root  # 保留签名供后续扩展（如 skill 级默认目录）

    if _looks_like_raw_cli(user_args):
        try:
            return shlex.split(user_args)
        except ValueError:
            return None

    spec = _resolve_cli_spec(skill_text, entry)
    if not spec or not spec.params:
        tokens = shlex.split(user_args) if user_args.strip() else []
        return tokens or None

    explicit_flags, remainder = _extract_explicit_flags(user_args)
    paths = _extract_paths(user_args)
    quoted = _extract_quoted(remainder)
    free_values = _collect_free_values(remainder, paths, quoted)
    hints = _parse_natural_hints(user_args)
    value_idx = 0

    argv: list[str] = []
    used_flags: set[str] = set()

    for param in spec.params:
        if param.positional:
            if paths:
                candidate = paths.pop(0)
                try:
                    argv.append(str(Path(candidate).resolve()))
                except OSError:
                    argv.append(candidate)
            elif param.required:
                guessed = _guess_param_value(param, hints, paths)
                if guessed is None:
                    return None
                argv.append(guessed)
            continue

        flag = param.name
        short = param.short
        val = explicit_flags.get(flag) or (short and explicit_flags.get(short))
        if val is None:
            val = _guess_param_value(param, hints, paths)
        if val is not None:
            argv.extend([flag, val])
            used_flags.add(flag)
            if short:
                used_flags.add(short)
            continue

        if param.required:
            if value_idx >= len(free_values):
                return None
            argv.extend([flag, free_values[value_idx]])
            value_idx += 1

    for key, val in explicit_flags.items():
        norm = _normalize_flag_key(key, spec)
        if norm and norm not in used_flags:
            argv.extend([norm, val])

    return argv if argv else None


def _ensure_requirements(skill_root: Path) -> None:
    req = skill_root / "requirements.txt"
    if not req.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:
        logger.warning("Skill 依赖安装失败: {}", exc)


def _run_subprocess(cmd: list[str], *, cwd: str | None, skill_name: str) -> SkillRunResult:
    command_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return SkillRunResult(ok=False, error="Skill 执行超时（300s）", command=command_str)
    except Exception as exc:
        return SkillRunResult(ok=False, error=f"Skill 执行失败: {exc}", command=command_str)

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    combined = stdout
    if stderr:
        combined = f"{stdout}\n\n{stderr}".strip() if stdout else stderr

    if proc.returncode != 0:
        return SkillRunResult(
            ok=False,
            output=combined,
            error=f"Skill 脚本退出码 {proc.returncode}",
            command=command_str,
        )

    header = f"**Skill `{skill_name}` 执行完成**\n\n```bash\n{command_str}\n```\n\n"
    body = combined or "（无输出）"
    return SkillRunResult(ok=True, output=header + body, command=command_str)


def _try_run_inline_python(
    skill_name: str,
    user_args: str,
    skill_text: str,
    skill_root: Path,
) -> SkillRunResult | None:
    template = _find_inline_python_template(skill_text)
    if not template:
        return None

    spec = _parse_cli_spec_from_skill(skill_text, "inline")
    values = _build_inline_values(user_args, spec)
    code = _fill_inline_template(template, values)
    if not code:
        return None

    _ensure_requirements(skill_root)
    return _run_subprocess(
        [sys.executable, "-c", code],
        cwd=str(skill_root),
        skill_name=skill_name,
    )


def _resolve_user_args(
    skill_name: str,
    skill_text: str,
    user_args: str,
    llm: BaseChatModel | None,
) -> tuple[str, str]:
    """返回 (effective_args, intent_reason)。"""
    body = (user_args or "").strip()
    if not body:
        return body, ""
    if _looks_like_raw_cli(body):
        return body, "raw_cli"
    if llm is not None:
        parsed = parse_skill_command_with_llm(llm, skill_name, skill_text, body)
        if parsed.ok:
            return parsed.cli_args, parsed.reason or "llm"
        logger.warning("Skill LLM 意图识别未成功，回退启发式: {}", parsed.error)
    return body, "heuristic"


def run_skill(
    skill_name: str,
    user_args: str,
    llm: BaseChatModel | None = None,
) -> SkillRunResult:
    resolved = resolve_skill(skill_name)
    if not resolved:
        return SkillRunResult(ok=False, error=f"未找到 Skill：{skill_name}", fallback_agent=True)

    skill_root, skill_md_path = resolved
    try:
        skill_text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return SkillRunResult(ok=False, error=f"读取 SKILL.md 失败: {exc}", fallback_agent=True)

    effective_args, intent_reason = _resolve_user_args(skill_name, skill_text, user_args, llm)

    entry = _find_entry_script(skill_root, skill_text)
    if not entry:
        inline_result = _try_run_inline_python(skill_name, effective_args, skill_text, skill_root)
        if inline_result is not None:
            inline_result.intent_reason = intent_reason
            return inline_result
        return SkillRunResult(ok=False, error="Skill 目录中未找到可执行脚本", fallback_agent=True)

    argv = _build_argv(entry, effective_args, skill_text, skill_root)
    if not argv:
        inline_result = _try_run_inline_python(skill_name, effective_args, skill_text, skill_root)
        if inline_result is not None:
            inline_result.intent_reason = intent_reason
            return inline_result
        return SkillRunResult(
            ok=False,
            error=(
                "无法根据 SKILL.md 解析命令参数。"
                "请使用文档中的 CLI 格式，或补充 scripts/ 入口脚本与参数说明表。"
            ),
            intent_reason=intent_reason,
            fallback_agent=True,
        )

    _ensure_requirements(skill_root)
    cmd = [sys.executable, str(entry), *argv]
    result = _run_subprocess(cmd, cwd=str(entry.parent), skill_name=skill_name)
    result.intent_reason = intent_reason
    return result


def can_run_skill(skill_name: str) -> bool:
    resolved = resolve_skill(skill_name)
    if not resolved:
        return False
    skill_root, skill_md_path = resolved
    try:
        skill_text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if _find_entry_script(skill_root, skill_text) is not None:
        return True
    return _find_inline_python_template(skill_text) is not None
