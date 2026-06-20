"""按 SKILL.md 说明直接执行 Skill 脚本。"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from src.ui.skill_catalog import load_skill_prompt, resolve_skill


@dataclass
class SkillRunResult:
    ok: bool
    output: str = ""
    command: str = ""
    error: str = ""
    fallback_agent: bool = False


_PATH_RE = re.compile(
    r'"([^"]+)"|\'([^\']+)\'|([A-Za-z]:\\(?:[^"\s]+(?:\\[^"\s]+)*))'
)
_SECTION_PATTERNS = [
    re.compile(r'--section\s+["\']([^"\']+)["\']', re.I),
    re.compile(r'(?:获取|提取|导出)\s*["\']?(\d+(?:\.\d+)*(?:\s+[\u4e00-\u9fff\w]+)?)', re.I),
    re.compile(r'(?:第\s*)?(\d+(?:\.\d+)+)\s*(?:章节|节|章)?', re.I),
    re.compile(r'章节\s*["\']?([^"\']+?)["\']?(?:\s|$|的)', re.I),
    re.compile(r'section\s+["\']?([^"\']+?)["\']?(?:\s|$)', re.I),
]


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


def _extract_paths(text: str) -> list[str]:
    paths: list[str] = []
    for m in _PATH_RE.finditer(text or ""):
        p = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if p and p not in paths:
            paths.append(p)
    return paths


def _extract_section(text: str) -> str:
    body = text or ""
    for pat in _SECTION_PATTERNS:
        m = pat.search(body)
        if m:
            section = (m.group(1) or "").strip()
            section = re.sub(r"(?:章节|节|章|的表格|表格)$", "", section).strip()
            if section:
                return section
    return ""


def _default_output(skill_root: Path, input_file: str, section: str) -> str:
    out_dir = skill_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    base = Path(input_file).stem
    safe = re.sub(r'[\\/:*?"<>|]', "_", section).replace(" ", "_")
    return str(out_dir / f"{base}_{safe}.xlsx")


def _build_argv(entry: Path, user_args: str, skill_root: Path) -> list[str] | None:
    """根据脚本 CLI 与用户参数构造 argv（不含 python 与脚本路径）。"""
    name = entry.name.lower()
    paths = _extract_paths(user_args)
    if not paths:
        return None

    input_file = str(Path(paths[0]).resolve())
    if not Path(input_file).is_file():
        return None

    section = _extract_section(user_args)
    if not section:
        return None

    if "doc_diff" in name or "doc-diff" in skill_root.name:
        output = _default_output(skill_root, input_file, section)
        for p in paths[1:]:
            if p.lower().endswith(".xlsx"):
                output = p
                break
        out_match = re.search(r'--output\s+["\']?([^\s"\']+)', user_args, re.I)
        if out_match:
            output = out_match.group(1)
        return [input_file, "--section", section, "--output", output]

    if entry.parent.name == "scripts":
        return [input_file, "--section", section]

    return None


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


def run_skill(skill_name: str, user_args: str) -> SkillRunResult:
    resolved = resolve_skill(skill_name)
    if not resolved:
        return SkillRunResult(ok=False, error=f"未找到 Skill：{skill_name}", fallback_agent=True)

    skill_root, skill_md_path = resolved
    try:
        skill_text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return SkillRunResult(ok=False, error=f"读取 SKILL.md 失败: {exc}", fallback_agent=True)

    entry = _find_entry_script(skill_root, skill_text)
    if not entry:
        return SkillRunResult(ok=False, error="Skill 目录中未找到可执行脚本", fallback_agent=True)

    argv = _build_argv(entry, user_args, skill_root)
    if not argv:
        return SkillRunResult(
            ok=False,
            error="无法从参数解析输入文件与章节，请使用：/skill \"文件路径\" 获取 2.1 章节",
            fallback_agent=True,
        )

    _ensure_requirements(skill_root)
    cmd = [sys.executable, str(entry), *argv]
    command_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(entry.parent),
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


def can_run_skill(skill_name: str) -> bool:
    resolved = resolve_skill(skill_name)
    if not resolved:
        return False
    skill_root, skill_md_path = resolved
    try:
        skill_text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return _find_entry_script(skill_root, skill_text) is not None
