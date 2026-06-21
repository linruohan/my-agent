# 日程 / 工作区

日历事件的读取与创建，数据以 JSON 文件存储在工作区目录。

## 源码位置

```
src/tools/workspace/
└── tools.py      # read_calendar, create_calendar_event
```

## Agent 工具

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `read_calendar` | 读取日历事件 | 否 |
| `create_calendar_event` | 创建日历事件 | 是 |

## 数据存储

- 文件：`data/workspace/calendar.json`
- 格式：JSON 数组，每项包含 title、start、end、description 等字段

## Web UI 万年历

Web 前端提供万年历组件：

| 文件 | 说明 |
|------|------|
| `web/js/calendar.js` | 日历渲染与交互 |
| `web/js/holidays.js` | 节假日数据 |
| `web/js/vendor/lunar.js` | 农历计算 |
| `web/css/calendar.css` | 日历样式 |

万年历支持：

- 月视图切换
- 农历显示
- 节假日标注
- 与 calendar.json 事件联动

## 工作区目录

`data/workspace/` 还包含：

| 路径 | 用途 |
|------|------|
| `knowledge/` | RAG 知识库文档 |
| `calendar.json` | 日历事件 |
| `todos.json.migrated` | 旧待办迁移标记 |

## 使用示例

Agent 对话：

- 「我这周有什么安排？」→ read_calendar
- 「下周三下午 2 点安排一个团队会议」→ create_calendar_event（需确认）
