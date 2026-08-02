"""持久化 Python 代码沙箱（常驻子进程 + 会话 pickle + 可选工具 RPC）。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

from src.infra.paths import DATA_DIR
from src.tools.code.tool_rpc import invoke_sandbox_tool, sandbox_tool_call_enabled

_SESSION_DIR = DATA_DIR / "workspace" / ".code_sessions"
_WORKER = Path(__file__).with_name("worker_main.py")
_DEFAULT_TIMEOUT = 30.0
_MAX_OUTPUT = 12000
_WORKER_IDLE_SEC = 600.0
_WORKER_CLEANUP_INTERVAL = 120.0

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

_workers_lock = threading.Lock()
_workers: dict[str, "_PersistentSandboxWorker"] = {}
_cleanup_started = False
_cleanup_stop = threading.Event()


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


def _persistent_enabled() -> bool:
    raw = (os.environ.get("AGENT_SANDBOX_PERSISTENT") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def reset_code_session(session_id: str = "default") -> None:
    path = _session_path(session_id)
    if path.is_file():
        path.unlink()
    sid = re.sub(r"[^\w.-]", "_", session_id or "default")[:64]
    with _workers_lock:
        worker = _workers.pop(sid, None)
    if worker is not None:
        worker.reset_and_shutdown()


def _drive_stdio(
    proc: subprocess.Popen[str],
    *,
    timeout: float,
) -> dict[str, Any]:
    """读取 worker stdout，处理 RPC，直到 RESULT 或超时。"""
    result: dict[str, Any] | None = None
    extra_lines: list[str] = []
    error_holder: list[BaseException] = []
    done = threading.Event()

    def _reader() -> None:
        nonlocal result
        assert proc.stdout is not None
        try:
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
                    break
                else:
                    extra_lines.append(line)
        except Exception as exc:
            error_holder.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=_reader, daemon=True, name="sandbox-stdio")
    thread.start()
    if not done.wait(timeout=timeout):
        try:
            proc.kill()
        except Exception:
            pass
        return {"stdout": "", "stderr": "", "error": f"执行超时（>{timeout}s）", "variables": []}
    thread.join(timeout=2)
    if error_holder:
        return {
            "stdout": "".join(extra_lines),
            "stderr": "",
            "error": str(error_holder[0]),
            "variables": [],
        }
    if result is None:
        err = ""
        try:
            if proc.stderr:
                err = proc.stderr.read() or ""
        except Exception:
            pass
        return {
            "stdout": "".join(extra_lines),
            "stderr": err,
            "error": "沙箱未返回结果",
            "variables": [],
        }
    if extra_lines:
        result["stdout"] = "".join(extra_lines) + str(result.get("stdout") or "")
    return result


class _PersistentSandboxWorker:
    def __init__(self, session_id: str, *, rpc: bool) -> None:
        self.session_id = session_id
        self.rpc = rpc
        self.session_path = _session_path(session_id)
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self.last_used = time.monotonic()

    def _start(self) -> None:
        mode = "rpc" if self.rpc else "plain"
        self._proc = subprocess.Popen(
            [sys.executable, str(_WORKER), str(self.session_path), "serve", mode],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

    def _ensure_alive(self) -> subprocess.Popen[str]:
        if self._proc is None or self._proc.poll() is not None:
            self._start()
        assert self._proc is not None
        return self._proc

    def execute(self, code: str, timeout: float) -> dict[str, Any]:
        with self._lock:
            self.last_used = time.monotonic()
            proc = self._ensure_alive()
            assert proc.stdin is not None
            try:
                proc.stdin.write(json.dumps({"op": "exec", "code": code}, ensure_ascii=False) + "\n")
                proc.stdin.flush()
            except Exception as exc:
                self._kill()
                return {"stdout": "", "stderr": "", "error": f"沙箱通信失败: {exc}", "variables": []}
            data = _drive_stdio(proc, timeout=timeout)
            if proc.poll() is not None and not data.get("error"):
                # worker 意外退出时下次重建
                self._proc = None
            elif data.get("error") and "超时" in str(data.get("error")):
                self._proc = None
            return data

    def reset_and_shutdown(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is None:
            return
        try:
            if proc.poll() is None and proc.stdin:
                proc.stdin.write(json.dumps({"op": "shutdown"}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=3)
        except Exception:
            pass
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass

    def _kill(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            proc.kill()
        except Exception:
            pass

    def idle_shutdown(self) -> None:
        self.reset_and_shutdown()


def _get_worker(session_id: str, *, rpc: bool) -> _PersistentSandboxWorker:
    global _cleanup_started
    sid = re.sub(r"[^\w.-]", "_", session_id or "default")[:64]
    with _workers_lock:
        worker = _workers.get(sid)
        if worker is None or worker.rpc != rpc:
            if worker is not None:
                worker.reset_and_shutdown()
            worker = _PersistentSandboxWorker(sid, rpc=rpc)
            _workers[sid] = worker
        if not _cleanup_started:
            threading.Thread(
                target=_worker_cleanup_loop,
                daemon=True,
                name="sandbox-idle-cleanup",
            ).start()
            _cleanup_started = True
        return worker


def _worker_cleanup_loop() -> None:
    while not _cleanup_stop.wait(_WORKER_CLEANUP_INTERVAL):
        now = time.monotonic()
        stale: list[_PersistentSandboxWorker] = []
        with _workers_lock:
            for sid, worker in list(_workers.items()):
                if now - worker.last_used > _WORKER_IDLE_SEC:
                    stale.append(_workers.pop(sid))
        for worker in stale:
            try:
                worker.idle_shutdown()
            except Exception:
                logger.debug("沙箱空闲清理失败", exc_info=True)


def shutdown_sandbox_workers() -> None:
    _cleanup_stop.set()
    with _workers_lock:
        workers = list(_workers.values())
        _workers.clear()
    for worker in workers:
        try:
            worker.reset_and_shutdown()
        except Exception:
            pass


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
        return _drive_stdio(proc, timeout=timeout)
    finally:
        Path(code_file).unlink(missing_ok=True)


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
    rpc = sandbox_tool_call_enabled()
    try:
        if _persistent_enabled():
            data = _get_worker(session_id, rpc=rpc).execute(body, limit)
        elif rpc:
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
