# 笔记管理

快速记录、查询、搜索和删除个人笔记，支持 Agent 工具调用与斜杠命令两种入口。

## 源码位置

```
src/tools/note/
├── tools.py      # add_note 工具
└── store.py      # NoteStore + handle_note_command
```

## Agent 工具

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `add_note` | 添加一条笔记 | 否 |

Agent 可通过自然语言「帮我记一下…」触发 `add_note`。

## 斜杠命令 `/note`

`handle_note_command(args)` 支持子命令：

| 子命令 | 用法 | 说明 |
|--------|------|------|
| add | `/note add 内容` 或 `/note 内容` | 添加笔记 |
| list | `/note list` | 列出最近笔记 |
| search | `/note search 关键词` | 搜索笔记 |
| rm | `/note rm <id>` | 删除指定笔记 |

## 数据存储

- 数据库：`data/app.db` 的 `notes` 表（SQLite）
- 字段：id、content、tags、created_at、updated_at

## 使用示例

```
/note 明天下午三点开会
/note list
/note search 开会
/note rm 3
```

或通过 Agent 对话：

- 「记一下：下周一把报告发给张总」
- 「我有哪些关于会议的笔记？」
