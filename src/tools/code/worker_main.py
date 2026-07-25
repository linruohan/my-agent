"""代码沙箱子进程：支持 call_tool RPC。"""

from __future__ import annotations

import io
import json
import pickle
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

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


def main() -> None:
    session_path = Path(sys.argv[1])
    code_path = Path(sys.argv[2])
    rpc_enabled = len(sys.argv) > 3 and sys.argv[3] == "rpc"
    code = code_path.read_text(encoding="utf-8")

    ns: dict = {"__name__": "__sandbox__"}
    if rpc_enabled:
        ns["call_tool"] = call_tool
    if session_path.is_file():
        try:
            ns.update(pickle.loads(session_path.read_bytes()))
        except Exception:
            pass  # 会话状态损坏时以空命名空间继续

    stdout = io.StringIO()
    stderr = io.StringIO()
    error = ""
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exec(compile(code, "<execute_code>", "exec"), ns)
    except Exception:
        error = traceback.format_exc()

    keep: dict = {}
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
        pass  # 沙箱子进程无法写会话时忽略，不影响本次执行结果

    payload = {
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "error": error,
        "variables": sorted(k for k in keep if k not in ("__builtins__",)),
    }
    _real_stdout().write(RESULT_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
    _real_stdout().flush()


if __name__ == "__main__":
    main()
