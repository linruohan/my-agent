"""持久化 Python 代码沙箱（子进程 + 会话 pickle + 可选工具 RPC）。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.paths import DATA_DIR
from src.tools.code.tool_rpc import invoke_sandbox_tool, sandbox_tool_call_enabled

_SESSION_DIR = DATA_DIR / "workspace" / ".code_sessions"
_WORKER = Path(__file__).with_name("worker_main.py")
_DEFAULT_TIMEOUT = 30.0
_MAX_OUTPUT = 12000

_BLOCKED_IMPORTS = frozenset({
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "ctypes",
    "multiprocessing",
    "importlib",
    "builtins",
    "__builtin__",
    "pickle",
    "marshal",
    "code",
    "pty",
    "fcntl",
    "resource",
    "signal",
    "winreg",
})

_IMPORT_RE = re.compile(r"(?m)^\s*(?:import|from)\s+([\w.]+)")
_RPC_PREFIX = "__AGENT_RPC__"
_RESULT_PREFIX = "__AGENT_RESULT__"


def session_dir() -> Path:
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSION_DIR


def _session_path(session_id: str) -> Path:
    safe = re.sub(r"[^\w.-]", "_", session_id or "default")[:64]
    return session_dir() / f"{safe}.pkl"


def _check_code(code: str) -> str | None:
    for match in _IMPORT_RE.finditer(code or ""):
        root = match.group(1).split(".")[0]
        if root in _BLOCKED_IMPORTS:
            return f"沙箱禁止 import {root}"
    if re.search(r"(?i)\b(__import__|eval\s*\(|exec\s*\(|compile\s*\()", code or ""):
        return "沙箱禁止使用 __import__/eval/exec/compile"
    return None


def reset_code_session(session_id: str = "default") -> None:
    path = _session_path(session_id)
    if path.is_file():
        path.unlink()


def _run_subprocess_plain(body: str, session_path: Path, timeout: float) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".py", delete=False) as tmp:
        tmp.write(body)
        code_file = tmp.name
    try:
        proc = subprocess.run(
            [sys.executable, str(_WORKER), str(session_path), code_file, "plain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    finally:
        Path(code_file).unlink(missing_ok=True)
    raw = (proc.stdout or "").strip()
    for line in raw.splitlines():
        if line.startswith(_RESULT_PREFIX):
            return json.loads(line[len(_RESULT_PREFIX) :])
    return {"stdout": raw, "stderr": proc.stderr or "", "error": "", "variables": []}


def _run_subprocess_rpc(body: str, session_path: Path, timeout: float) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".py", delete=False) as tmp:
        tmp.write(body)
        code_file = tmp.name

    result: dict[str, Any] | None = None
    extra_lines: list[str] = []
    proc: subprocess.Popen[str] | None = None

    def _reader() -> None:
        nonlocal result
        assert proc is not None and proc.stdout is not None
        for line in proc.stdout:
            if line.startswith(_RPC_PREFIX):
                if proc.stdin is None:
                    continue
                try:
                    req = json.loads(line[len(_RPC_PREFIX) :].strip())
                    res = invoke_sandbox_tool(req.get("name", ""), req.get("args") or {})
                    proc.stdin.write(json.dumps({"result": res}, ensure_ascii=False) + "\n")
                    proc.stdin.flush()
                except Exception as exc:
                    proc.stdin.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
                    proc.stdin.flush()
            elif line.startswith(_RESULT_PREFIX):
                result = json.loads(line[len(_RESULT_PREFIX) :].strip())
            else:
                extra_lines.append(line)

    try:
        proc = subprocess.Popen(
            [sys.executable, str(_WORKER), str(session_path), code_file, "rpc"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        proc.wait(timeout=timeout)
        thread.join(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"stdout": "", "stderr": "", "error": f"执行超时（>{timeout}s）", "variables": []}
    finally:
        Path(code_file).unlink(missing_ok=True)

    if result is None:
        err = (proc.stderr.read() if proc.stderr else "") if proc else ""
        return {
            "stdout": "".join(extra_lines),
            "stderr": err,
            "error": "沙箱未返回结果",
            "variables": [],
        }
    if extra_lines:
        result["stdout"] = "".join(extra_lines) + str(result.get("stdout") or "")
    return result


def execute_code_in_sandbox(
    code: str,
    *,
    session_id: str = "default",
    timeout: float | None = None,
) -> str:
    blocked = _check_code(code)
    if blocked:
        return blocked

    body = (code or "").strip()
    if not body:
        return "代码为空。"

    session_path = _session_path(session_id)
    limit = timeout or _DEFAULT_TIMEOUT
    try:
        if sandbox_tool_call_enabled():
            data = _run_subprocess_rpc(body, session_path, limit)
        else:
            data = _run_subprocess_plain(body, session_path, limit)
    except Exception as exc:
        logger.exception("代码沙箱启动失败")
        return f"沙箱启动失败: {exc}"

    parts: list[str] = []
    if data.get("stdout"):
        parts.append(str(data["stdout"]).rstrip())
    if data.get("stderr"):
        parts.append(f"[stderr]\n{str(data['stderr']).rstrip()}")
    if data.get("error"):
        parts.append(f"[error]\n{str(data['error']).rstrip()}")
    vars_ = data.get("variables") or []
    if vars_:
        parts.append(f"[session 变量] {', '.join(vars_[:20])}")

    out = "\n".join(parts).strip() or "（执行完成，无输出）"
    if len(out) > _MAX_OUTPUT:
        out = out[: _MAX_OUTPUT - 20] + "\n…（输出已截断）"
    return out
