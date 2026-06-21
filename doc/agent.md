# Agent 核心

Agent 基于 LangGraph 预构建的 ReAct Agent，实现「思考 → 行动 → 观察」循环，支持流式输出与 Human-in-the-loop（HITL）确认。

## 核心文件

| 文件 | 说明 |
|------|------|
| `src/agent/graph.py` | 构建 Agent 图 |
| `src/agent/runner.py` | 异步执行与事件流 |
| `src/agent/hitl.py` | 敏感操作审批逻辑 |
| `src/agent/state.py` | 状态 TypedDict 定义 |

## 图构建

`build_agent_graph(llm, checkpoint_path)` 流程：

1. 打开 SQLite Checkpoint 连接（`data/checkpoints/agent.db`）
2. 从 `config/app.yaml` 读取 `system_prompt`
3. 注入当前日期与搜索行为约束（`build_system_prompt`）
4. `get_enabled_tools()` 按 `config/tools.yaml` 过滤启用的工具
5. `wrap_tools_for_process()` 可选包装为子进程执行
6. `create_react_agent(llm, tools, prompt, checkpointer, interrupt_before=["tools"])`

**关键设计**：在 `tools` 节点前设置中断（`interrupt_before=["tools"]`），每次工具调用前暂停，检查是否需要用户确认。

## System Prompt

基础 Prompt 定义在 `config/app.yaml` 的 `agent.system_prompt`，运行时追加：

- 当前日期与年份
- 搜索回答规则（时效性内容必须 web_search、禁止粘贴原始摘要等）
- 本地文件操作指引
- 敏感操作确认提示

## 执行流程（AgentRunner）

```
run_async(user_input, thread_id)
    │
    ▼
后台线程 _worker()
    │
    ▼
_stream_loop(initial_state)
    │
    ├─ graph.stream(..., stream_mode="messages")
    │     ├─ AIMessage → event: token / tool_call
    │     └─ ToolMessage → event: tool_result
    │
    ├─ 检查 snapshot.next 是否含 "tools"（中断态）
    │
    └─ needs_user_approval(tool_name)?
          ├─ 是 → event: approval_required，等待 UI 响应
          │         ├─ 批准 → Command(resume=True) 继续执行
          │         └─ 拒绝 → 写入 ToolMessage 拒绝说明
          └─ 否 → 自动继续
```

## 事件类型

AgentRunner 通过 `event_queue` 向 UI 推送以下事件：

| 事件 | 数据 | 说明 |
|------|------|------|
| `start` | `{thread_id}` | 开始执行 |
| `token` | `{content}` | LLM 流式 token |
| `tool_call` | `{name, args}` | 工具调用请求 |
| `tool_result` | `{name, content}` | 工具返回结果 |
| `approval_required` | `{tool_name, args, risk}` | 需用户确认 |
| `done` | `{thread_id}` | 执行完成 |
| `error` | `{message}` | 执行出错 |

UI 侧 `AssistantController.poll_agent_events()` 消费这些事件，经 `WebChatBridge` 推送到前端 `window.ChatApp.handleEvent()`。

## Human-in-the-loop

敏感工具在 `config/tools.yaml` 中标记 `requires_confirmation: true`：

| 风险级别 | 示例操作 |
|----------|----------|
| low | 读取文件、搜索、查询任务 |
| medium | 创建文件、复制、重命名、完成任务 |
| high | 写入、删除、移动文件/目录 |

审批 UI 在 Web 聊天区弹出确认卡片，用户点击「批准」或「拒绝」后调用 `AgentRunner.resume_after_approval(approved=True/False)`。

## 工具执行隔离

`src/tools/process_wrap.py` + `src/tools/tool_worker.py`：

- 可选将工具调用放到子进程执行
- 避免长时间 I/O 或 CPU 密集操作阻塞 UI 线程
- 进程池由 `src/infra/process_executor.py` 管理生命周期

## 与输入路由的关系

并非所有用户输入都进入 Agent。以下场景走独立管道：

- 斜杠命令（`/note`、`/tsk`、`/search` 等）
- 明确的搜索意图（规则或 LLM 分类为 `INTENT_SEARCH`）
- 天气查询、链接摘要、OCR

只有 `INTENT_AGENT` 才会调用 `AgentRunner.run_async()`。详见 [input-routing.md](input-routing.md)。
