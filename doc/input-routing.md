# 输入路由与斜杠命令

用户输入在到达 Agent 之前，先经过意图识别分流到不同的处理管道。

## 源码位置

```
src/ui/input/
├── intent.py     # 意图识别主逻辑
├── compose.py    # 消息拼装、URL 提取
└── history.py    # 输入历史
```

## 意图类型

| 意图常量 | 说明 | 处理方式 |
|----------|------|----------|
| `INTENT_AGENT` | 通用对话 | LangGraph ReAct Agent |
| `INTENT_SEARCH` | 网页搜索 | 独立搜索管道 |
| `INTENT_WEATHER` | 天气查询 | 天气 HTML 渲染 |
| `INTENT_SLASH_WEATHER` | `/weather` 命令 | 天气 HTML 渲染 |
| `INTENT_LINK` | 含 URL 的消息 | 链接抓取 + LLM 摘要 |
| `INTENT_OCR` | 图片 OCR | Windows OCR / PaddleOCR |
| `INTENT_SLASH_NOTE` | `/note` 命令 | 笔记本地命令 |
| `INTENT_SLASH_TASK` | `/tsk` 命令 | 任务本地命令 |
| `INTENT_SLASH_CACHE` | `/cache` 命令 | 搜索缓存管理 |
| `INTENT_SLASH_SKILL` | `/<skill>` 命令 | Skill 脚本执行 |
| `INTENT_SLASH_OCR` | `/ocr` 命令 | 图片 OCR |

## 识别优先级

`resolve_input_intent()` 按以下顺序判定：

1. **斜杠命令** — 以 `/` 开头，匹配系统命令或 Skill 名称
2. **附件 OCR** — 消息含图片且无其他明确意图
3. **URL 检测** — 消息含 http(s) 链接 → 链接摘要
4. **规则匹配** — 天气关键词、笔记前缀等正则
5. **LLM 分类** — 调用 LLM 判断 search vs agent（可选）
6. **默认** — `INTENT_AGENT`

## 斜杠命令详解

### 系统内置命令

| 命令 | 子命令/参数 | 功能 |
|------|-------------|------|
| `/note` | add / list / search / rm | 笔记管理 |
| `/tsk` | add / list / done / rm | 任务管理 |
| `/search` | `<query>` | 直接网页搜索 |
| `/weather` | `[city] [range]` | 天气预报 |
| `/cache` | list / clear | 搜索缓存管理 |
| `/ocr` | — | 触发图片 OCR |

### Skill 命令

扫描用户配置的 Skill 目录，每个含 `SKILL.md` 的子目录注册为 `/<folder-name>` 斜杠命令。详见 [skills.md](skills.md)。

## 斜杠菜单

Web 前端 `composer.js` 在用户输入 `/` 时弹出斜杠命令菜单：

- 显示系统命令 + 已扫描的 Skill
- 支持模糊搜索过滤
- 选中后自动补全命令

目录数据来源：`src/ui/skill/catalog.py` 的 `build_slash_catalog()`

## 链接摘要

当消息包含 URL 时：

1. `src/ui/link/fetch.py` 抓取页面内容（httpx 或 playwright）
2. `src/ui/link/summarize.py` 调用 LLM 生成摘要
3. 结果以助手消息展示

用户可附加指令，如「总结这个链接的主要观点 https://...」

## 输入历史

- 存储：`data/input_history.json`
- 支持上下键翻阅历史输入
- `src/ui/input/history.py` 管理读写

## InputIntent 数据结构

```python
@dataclass
class InputIntent:
    kind: str                    # 意图类型
    search_query: str = ""       # 搜索关键词
    urls: list[str] = []         # 检测到的 URL
    link_instruction: str = ""   # 链接摘要指令
    note_content: str = ""       # 笔记内容
    slash_cmd: str = ""          # 斜杠命令名
    slash_args: str = ""         # 斜杠命令参数
    skill_name: str = ""         # Skill 名称
    weather_city_code: str = ""  # 天气城市代码
    weather_range: str = "7d"    # 预报范围
    reason: str = ""             # 识别原因（调试用）
```
