# 配置与数据存储

## 配置文件

所有默认配置位于 `config/` 目录，用户覆盖存储在 `data/user_settings.yaml`。

### config/app.yaml

应用全局配置：

```yaml
app:
  title: "个人助理 Agent"
  theme: "dark"
  window_width: 1100
  window_height: 720

paths:
  checkpoints: "data/checkpoints"
  workspace: "data/workspace"
  vectorstore: "data/vectorstore"

agent:
  system_prompt: |
    你是一个高效、友好的个人助理...
  max_history_messages: 40
```

### config/llm_providers.yaml

LLM Provider 定义，详见 [llm.md](llm.md)。

### config/tools.yaml

工具启用状态、风险级别、确认要求。每个工具条目：

```yaml
tool_name:
  enabled: true
  risk: low          # low | medium | high
  requires_confirmation: false
```

### config/search.yaml

搜索引擎、RAG embedding、搜索缓存配置。

### config/files.yaml

文件工具 search_roots、CLI 偏好、大小限制。

### config/weather.yaml

默认城市代码、预报天数、超时。

## 用户设置

`data/user_settings.yaml` 覆盖默认配置：

```yaml
llm:
  provider: deepseek        # 覆盖 default_provider

ui:
  theme: catppuccin
  skill_dirs:
    - "D:/my-skills"

task:
  owner: "张三"
```

## 密钥存储

API Key 存储优先级：

1. **Windows keyring**（推荐）
2. `data/secrets.json`（fallback）

管理逻辑在 `src/infra/user_settings.py`。

## 运行时数据

| 路径 | 格式 | 用途 |
|------|------|------|
| `data/sessions.db` | SQLite | 会话列表 + 聊天事件 JSON |
| `data/checkpoints/agent.db` | SQLite | LangGraph Agent Checkpoint |
| `data/task.db` | SQLite | 待办任务 |
| `data/note.db` | SQLite | 笔记 |
| `data/search_cache.db` | SQLite | 搜索回答缓存 |
| `data/vectorstore/` | FAISS + JSON | 向量索引与元数据 |
| `data/workspace/calendar.json` | JSON | 日历事件 |
| `data/workspace/knowledge/` | 文件目录 | RAG 知识库文档 |
| `data/input_history.json` | JSON | 输入框历史 |
| `data/user_settings.yaml` | YAML | 用户偏好 |
| `data/secrets.json` | JSON | API Key（fallback） |

## 路径解析

`src/infra/paths.py` 定义：

| 常量 | 路径 |
|------|------|
| `PROJECT_ROOT` | 项目根目录 |
| `CONFIG_DIR` | `config/` |
| `DATA_DIR` | `data/` |
| `THEMES_DIR` | `themes/` |
| `WEB_DIR` | `web/` |

所有路径相对于 `PROJECT_ROOT` 解析，支持 `~` 展开。

## 配置加载

`src/infra/config.py` 提供：

| 函数 | 说明 |
|------|------|
| `load_app_config()` | 加载 app.yaml |
| `load_tools_config()` | 加载 tools.yaml |
| `load_search_config()` | 加载 search.yaml |
| `load_files_config()` | 加载 files.yaml |
| `load_weather_config()` | 加载 weather.yaml |
| `load_llm_providers_config()` | 加载 llm_providers.yaml |

配置在首次调用时加载并缓存，修改 YAML 后需重启应用生效。

## 日志

- 框架：loguru
- 初始化：`src/infra/logger.py` 的 `setup_logger()`
- 在 `main.py` 启动时调用
