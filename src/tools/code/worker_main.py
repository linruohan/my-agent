"""代码沙箱子进程：支持 call_tool RPC 与常驻 serve 模式。"""

from __future__ import annotations

import io
import json
import pickle
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

RPC_PREFIX = "__AGENT_RPC__"
RESULT_PREFIX = "__AGENT_RESULT__"


def _real_stdout():
    return getattr(sys, "__stdout__", sys.stdout)


def call_tool(name: str, **kwargs):
    """沙箱内调用 Agent 工具（由父进程代理执行）。"""
    req = json.dumps({"name": name, "args": kwargs}, ensure_ascii=False)
    out = _real_stdout()
    out.write(RPC_PREFIX + req + "\n")
    out.flush()
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError("工具 RPC 通道已关闭")
    data = json.loads(line)
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data.get("result")


def _load_session(session_path: Path) -> dict[str, Any]:
    if not session_path.is_file():
        return {}
    try:
        data = pickle.loads(session_path.read_bytes())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _persist_session(ns: dict[str, Any], session_path: Path) -> list[str]:
    keep: dict[str, Any] = {}
    for key, val in ns.items():
        if key.startswith("_") or key == "call_tool":
            continue
        try:
            pickle.dumps(val)
            keep[key] = val
        except Exception:
            keep[key] = repr(val)
    try:
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_bytes(pickle.dumps(keep))
    except Exception:
        pass
    return sorted(k for k in keep if k not in ("__builtins__",))


def _exec_code(code: str, ns: dict[str, Any]) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    error = ""
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exec(compile(code, "<execute_code>", "exec"), ns)
    except Exception:
        error = traceback.format_exc()
    return {
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "error": error,
    }


def _emit_result(payload: dict[str, Any]) -> None:
    _real_stdout().write(RESULT_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
    _real_stdout().flush()


def _new_namespace(rpc_enabled: bool) -> dict[str, Any]:
    ns: dict[str, Any] = {"__name__": "__sandbox__"}
    if rpc_enabled:
        ns["call_tool"] = call_tool
    return ns


def run_once(session_path: Path, code: str, rpc_enabled: bool) -> None:
    ns = _new_namespace(rpc_enabled)
    ns.update(_load_session(session_path))
    result = _exec_code(code, ns)
    variables = _persist_session(ns, session_path)
    result["variables"] = variables
    _emit_result(result)


def serve_loop(session_path: Path, rpc_enabled: bool) -> None:
    """常驻模式：stdin 每行一个 JSON 请求。"""
    ns = _new_namespace(rpc_enabled)
    ns.update(_load_session(session_path))
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            req = json.loads(text)
        except json.JSONDecodeError:
            _emit_result({"stdout": "", "stderr": "", "error": "无效请求 JSON", "variables": []})
            continue
        op = str(req.get("op") or "")
        if op == "shutdown":
            _persist_session(ns, session_path)
            break
        if op == "reset":
            ns = _new_namespace(rpc_enabled)
            try:
                session_path.unlink(missing_ok=True)
            except OSError:
                pass
            _emit_result({"stdout": "", "stderr": "", "error": "", "variables": [], "ok": True})
            continue
        if op == "ping":
            _emit_result({"stdout": "", "stderr": "", "error": "", "variables": [], "ok": True})
            continue
        if op != "exec":
            _emit_result({"stdout": "", "stderr": "", "error": f"未知操作: {op}", "variables": []})
            continue
        code = str(req.get("code") or "")
        result = _exec_code(code, ns)
        variables = _persist_session(ns, session_path)
        result["variables"] = variables
        _emit_result(result)


def main() -> None:
    session_path = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "plain"
    if mode == "serve":
        rpc_enabled = len(sys.argv) > 3 and sys.argv[3] == "rpc"
        serve_loop(session_path, rpc_enabled)
        return

    # 兼容一次性模式：worker session_path code_file [plain|rpc]
    code_path = Path(sys.argv[2])
    rpc_enabled = len(sys.argv) > 3 and sys.argv[3] == "rpc"
    code = code_path.read_text(encoding="utf-8")
    run_once(session_path, code, rpc_enabled)


if __name__ == "__main__":
    main()
