# 任务管理

待办任务的创建、查询、完成、删除，支持自然语言解析、到期提醒和 Windows Toast 通知。

## 源码位置

```
src/tools/task/
├── tools.py      # add_task, list_tasks, search_tasks, complete_task, delete_task
├── store.py      # TaskStore + handle_task_command
├── parse.py      # 自然语言任务解析
└── notify.py     # TaskReminderService + Windows Toast

src/ui/ (相关)
└── task_scheduler 集成在 AssistantController
```

## Agent 工具

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `add_task` | 创建待办 | 否 |
| `list_tasks` | 列出待办 | 否 |
| `search_tasks` | 搜索待办 | 否 |
| `complete_task` | 标记完成 | 是 |
| `delete_task` | 删除待办 | 是 |

## 斜杠命令 `/tsk`

| 子命令 | 用法 | 说明 |
|--------|------|------|
| add | `/tsk add 买牛奶 明天` | 添加任务 |
| list | `/tsk list` | 列出待办 |
| done | `/tsk done <id>` | 标记完成 |
| rm | `/tsk rm <id>` | 删除任务 |

## 自然语言解析

`parse.py` 支持从自然语言提取：

- 任务标题
- 截止日期（「明天」「下周五」「3月15日」等）
- 优先级（高/中/低）
- 负责人（owner）

示例：

- 「提醒我明天下午买牛奶」→ title=买牛奶, due=明天下午
- 「下周五前完成报告，高优先级」→ title=完成报告, due=下周五, priority=high

## 到期提醒

`TaskReminderService` 后台定时检查：

- 扫描 `data/task.db` 中未完成的到期任务
- 到期时发送 Windows Toast 通知（`win11toast`）
- 可在用户设置中配置 owner 过滤

## 数据存储

- 数据库：`data/task.db`（SQLite）
- 字段：id、title、description、due_date、priority、status、owner、created_at、attachments

## 遗留迁移

旧版 `data/workspace/todos.json` 已迁移至 SQLite，迁移标记文件为 `todos.json.migrated`。

## 使用示例

Agent 对话：

- 「帮我创建一个任务：周五前提交季度报告」
- 「我有哪些未完成的待办？」
- 「把任务 5 标记为完成」

斜杠命令：

```
/tsk add 复习Python 后天
/tsk list
/tsk done 2
```
