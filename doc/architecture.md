# 系统架构

## 整体分层

```
┌─────────────────────────────────────────────────────────┐
│  表现层    web/ (HTML/CSS/JS) + pywebview               │
├─────────────────────────────────────────────────────────┤
│  控制层    src/ui/app.py — AssistantController          │
│            意图路由、会话管理、事件轮询                     │
├─────────────────────────────────────────────────────────┤
│  Agent 层  src/agent/ — LangGraph ReAct + HITL          │
├─────────────────────────────────────────────────────────┤
│  工具层    src/tools/ — 文件/搜索/RAG/任务/笔记/天气…   │
├─────────────────────────────────────────────────────────┤
│  基础设施  src/infra/ — 配置、路径、日志、进程池          │
│            src/llm/ — LLM Provider 工厂                  │
│            src/memory/ — RAG、搜索缓存                     │
└─────────────────────────────────────────────────────────┘
```

## 启动流程

1. `main.py` → `setup_logger()` → `run_app()`
2. `run_app()` 创建 `AssistantController`，初始化 SessionStore、TaskStore、NoteStore、SearchCache
3. `build_agent_graph()` 构建 LangGraph Agent 图
4. 创建 pywebview 窗口，加载 `dist/web/index.html`（或 `legacy/web`）
5. 启动后台线程 `poll_agent_events()`，每 50ms 从事件队列取 Agent 事件推送到前端

## 消息处理流程

```
用户输入（Web Composer）
    │
    ▼
AppApi.send_message()
    │
    ▼
AssistantController._process_send_message()
    │
    ▼
resolve_input_intent()  ── 斜杠命令 / 规则意图
    │
    ├─ INTENT_SLASH_*     → 本地斜杠命令处理（含 Skill）
    ├─ INTENT_WEATHER     → 天气 HTML 渲染
    ├─ INTENT_LINK        → 链接抓取 + LLM 摘要
    ├─ INTENT_OCR         → 图片 OCR
    ├─ INTENT_SEARCH      → 仅 /search 命令 → 搜索管道 / 缓存命中
    └─ INTENT_AGENT       → 先查搜索缓存 → 未命中则 AgentRunner.run_async()
                                │
                                ▼
                          LangGraph ReAct 循环
                                │
                    ┌───────────┴───────────┐
                    │ interrupt_before tools │
                    │ 需确认 → UI 审批      │
                    └───────────┬───────────┘
                                ▼
                          工具执行 → 流式 token
                                │
                                ▼
                          WebChatBridge → JS handleEvent
```

## 关键模块与文件

| 模块 | 路径 | 职责 |
|------|------|------|
| 入口 | `main.py` | CLI 启动 |
| 控制器 | `src/ui/app.py` | 核心业务编排 |
| 意图识别 | `src/ui/input/intent.py` | 斜杠/规则/LLM 分类 |
| Agent 图 | `src/agent/graph.py` | 构建 ReAct Agent |
| Agent 执行 | `src/agent/runner.py` | 流式执行、事件队列 |
| HITL | `src/agent/hitl.py` | 敏感操作确认 |
| 工具注册 | `src/tools/__init__.py` | 汇总所有工具 |
| Web 桥接 | `src/ui/web_bridge.py` | Python → JS 事件 |
| 会话存储 | `src/ui/session_store.py` | SQLite 会话持久化 |
| LLM 工厂 | `src/llm/factory.py` | Provider 实例化 |

## 线程模型

- **UI 主线程**：pywebview 事件循环
- **Agent 工作线程**：`AgentRunner` 在后台线程执行 LangGraph stream
- **事件轮询线程**：`poll_agent_events()` 从 `event_queue` 取事件，通过 `evaluate_js` 推送到前端
- **工具子进程**（可选）：`process_wrap.py` 将部分工具放到子进程，避免阻塞 GIL

## Agent 状态持久化

- 使用 LangGraph `SqliteSaver`，数据库路径 `data/checkpoints/agent.db`
- 每个会话对应一个 `thread_id`，Agent 可在同一会话内保持上下文
- Checkpoint 保存消息历史与图状态，支持中断恢复

## 扩展点

| 扩展方式 | 说明 |
|----------|------|
| 新增工具 | 在 `src/tools/` 下新建模块，注册到 `__init__.py`，配置 `tools.yaml` |
| 新增 Provider | 在 `config/llm_providers.yaml` 添加条目 |
| 新增 Skill | 在 Skill 目录放置 `SKILL.md` + 脚本 |
| 新增斜杠命令 | 在 `intent.py` 和 `catalog.py` 注册 |
| 新增主题 | 在 `themes/` 下添加 JSON 主题文件 |
