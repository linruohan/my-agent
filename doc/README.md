# my-agent 功能总览

**my-agent** 是一个基于 LangChain / LangGraph 的 Windows 桌面个人助理。用户通过自然语言与 Agent 对话，完成待办管理、日程查询、网页搜索、本地文件操作、知识库问答等日常事务。

## 快速开始

```bash
# 安装依赖
pip install -e .

# 启动应用
my-agent
# 或
python main.py
```

首次使用需在设置面板配置 LLM Provider 的 API Key（支持 DeepSeek、OpenAI、通义千问、Ollama 等）。

## 核心能力一览

| 能力域 | 说明 | 详细文档 |
|--------|------|----------|
| Agent 推理 | LangGraph ReAct 循环，流式输出，Human-in-the-loop 确认 | [agent.md](agent.md) |
| 任务管理 | 创建/查询/完成/删除待办，自然语言解析，到期提醒 | [tools-task.md](tools-task.md) |
| 笔记 | 快速记录、列表、搜索、删除 | [tools-note.md](tools-note.md) |
| 日程 | 读取/创建日历事件（JSON 存储） | [tools-workspace.md](tools-workspace.md) |
| 网页搜索 | Bing/百度/auto，查询增强，结果缓存 | [tools-web-search.md](tools-web-search.md) |
| 知识库 RAG | 本地文档向量化检索（FAISS + fastembed） | [tools-rag.md](tools-rag.md) |
| 本地文件 | 搜索、读写、复制/移动/删除等 20+ 工具 | [tools-file.md](tools-file.md) |
| 天气 | 中国天气网预报，支持 iframe 渲染 | [tools-weather.md](tools-weather.md) |
| 聊天 UI | pywebview + Web 前端，多会话、主题、Markdown | [ui.md](ui.md) |
| 输入路由 | 斜杠命令、搜索管道、链接摘要、OCR 等 | [input-routing.md](input-routing.md) |
| Skill 扩展 | 扫描 SKILL.md，以斜杠命令执行脚本 | [skills.md](skills.md) |
| 配置与数据 | YAML 配置、SQLite 存储、用户设置 | [config-data.md](config-data.md) |
| Gateway | HTTP/Telegram/Discord/Slack、HITL、webhook | [gateway.md](gateway.md) |
| 平台能力 | Windows OCR、Toast 通知（语音规划中） | [platform.md](platform.md) |

## 系统架构

```
main.py
  └─ run_app()                    # src/ui/app.py
       ├─ AssistantController     # 核心控制器
       │    ├─ SessionStore        # 会话持久化
       │    ├─ AgentRunner         # Agent 后台执行
       │    └─ WebChatBridge       # Python → JS 事件桥
       ├─ AppApi                   # pywebview js_api
       └─ webview + web/index.html # Web 聊天界面
```

用户消息不总是走 Agent。控制器先通过**意图识别**分流：

- **斜杠命令**（`/note`、`/tsk`、`/search` 等）→ 本地命令处理
- **搜索意图** → 独立搜索管道（可命中缓存）
- **天气 / 链接 / OCR** → 专用处理器
- **其余** → LangGraph ReAct Agent

详见 [architecture.md](architecture.md)。

## 工具清单

Agent 可调用的工具在 `config/tools.yaml` 中配置启用状态与风险级别。完整列表见 [tools-file.md](tools-file.md) 及各工具文档。

| 类别 | 工具数 | 需确认的操作 |
|------|--------|--------------|
| 本地文件 | 20 | 写入、删除、移动、重命名等 |
| 网页搜索 | 1 | — |
| 知识库 | 1 | — |
| 笔记 | 1 | — |
| 任务 | 5 | 完成、删除 |
| 日历 | 2 | 创建事件 |
| 天气 | 1 | — |

## 斜杠命令

| 命令 | 功能 |
|------|------|
| `/note` | 笔记管理（add / list / search / rm） |
| `/tsk` | 任务管理（add / list / done / rm） |
| `/search <query>` | 直接触发网页搜索 |
| `/weather [城市]` | 天气预报 |
| `/cache` | 搜索缓存管理 |
| `/metrics` | 耗时指标查看与导出 |
| `/ocr` | 图片文字识别 |
| `/<skill-name>` | 执行 Skill 目录中的脚本 |

## 配置层次

1. **默认配置**：`config/*.yaml`（随项目分发）
2. **用户覆盖**：`data/user_settings.yaml`（主题、Provider、Skill 目录等）
3. **密钥存储**：Windows keyring 或 `data/secrets.json`

## 数据文件

| 路径 | 用途 |
|------|------|
| `data/app.db` | 统一应用库（会话、任务、笔记、搜索缓存、Gateway、Cron、学习记录等） |
| `data/checkpoints/agent.db` | LangGraph Agent Checkpoint |
| `data/vectorstore/` | FAISS 向量索引 |
| `data/workspace/` | 日历、知识库文档、旧版扁平 MEMORY 兼容 |

## 技术栈

- **Agent**：LangChain + LangGraph（ReAct + SQLite Checkpoint）
- **UI**：pywebview + HTML/CSS/JS（23 套主题）
- **向量检索**：FAISS + fastembed（本地 embedding）
- **Python**：>= 3.11, < 3.14

## 相关文档

- 原始设计文档：[../个人助理Agent设计文档.md](../个人助理Agent设计文档.md)
- 各模块详细说明：见本目录下各 `.md` 文件
