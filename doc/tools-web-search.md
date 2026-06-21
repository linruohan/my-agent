# 网页搜索

提供 Bing / 百度搜索能力，支持查询增强、结果去重、Python 文档补全，以及搜索回答缓存。

## 源码位置

```
src/tools/web/
├── tools.py      # web_search 工具定义
└── core.py       # 搜索引擎实现、查询增强

src/ui/search_turn.py   # 独立搜索管道（非 Agent 路径）
src/memory/search_cache/  # 搜索回答缓存
```

## 工具

| 工具 | 说明 |
|------|------|
| `web_search` | 执行网页搜索，返回结构化摘要 |

## 搜索引擎

配置在 `config/search.yaml`：

| 引擎 | 说明 |
|------|------|
| `bing` | Bing 搜索 |
| `baidu` | 百度搜索 |
| `auto` | 自动选择（默认） |

### 查询增强

- `auto_enrich_query: true` 时自动为查询补充当前年份或「最新」
- Python 相关查询自动补全文档站点限定

## 两种搜索路径

### 1. Agent 工具调用

用户在对话中提问时效性内容，Agent 调用 `web_search` 工具，结果整合进回复。

### 2. 独立搜索管道

当意图识别为 `INTENT_SEARCH`（含 `/search` 斜杠命令）时，走 `search_turn.py` 独立管道：

- 不经过 Agent ReAct 循环
- 直接调用搜索引擎 + LLM 生成回答
- 更快响应简单搜索请求

## 搜索缓存

`src/memory/search_cache/` 提供相似 query 缓存：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `enabled` | true | 是否启用 |
| `text_similarity_threshold` | 0.65 | 相似度阈值 |
| `ttl_days` | 7 | 缓存有效期 |
| `max_entries` | 100 | 最大条目数 |

缓存存储在 `data/search_cache.db`。用户可通过 `/cache` 斜杠命令管理（查看/清除）。

## 配置

`config/search.yaml`：

```yaml
search:
  default_engine: auto
  max_results: 5
  timeout: 15
  auto_enrich_query: true

cache:
  enabled: true
  db_path: "data/search_cache.db"
  text_similarity_threshold: 0.65
  ttl_days: 7
  max_entries: 100
```

## 使用示例

- 自然语言：「Python 3.13 有什么新特性？」→ Agent 调用 web_search
- 斜杠命令：`/search LangGraph checkpoint 用法` → 独立搜索管道
- 缓存命中：相似问题再次提问时直接返回缓存回答
