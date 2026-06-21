# 用户界面

应用 UI 基于 **pywebview + Web 前端**，Python 侧通过桥接层与 JavaScript 通信。

## 架构

```
pywebview 窗口
  └─ web/index.html
       ├─ CSS: app.css, calendar.css, fonts-lxgw.css
       └─ JS:
            ├─ app.js       — API 桥、主题、设置
            ├─ chat.js      — 消息气泡、Markdown、工具卡片
            ├─ composer.js  — 输入框、斜杠菜单、附件
            ├─ sessions.js  — 会话列表
            └─ calendar.js  — 万年历
```

## Python 桥接

| 文件 | 说明 |
|------|------|
| `src/ui/app.py` | `AssistantController` + `AppApi` + `run_app()` |
| `src/ui/web_bridge.py` | `WebChatBridge`：Python → JS 事件推送 |

### AppApi（js_api）

暴露给前端的 Python 方法：

| 方法 | 说明 |
|------|------|
| `send_message(payload)` | 发送用户消息 |
| `approval_response(approved)` | HITL 审批响应 |
| `new_session()` | 新建会话 |
| `switch_session(id)` | 切换会话 |
| `delete_session(id)` | 删除会话 |
| `get_sessions()` | 获取会话列表 |
| `get_settings()` | 读取用户设置 |
| `save_settings(data)` | 保存用户设置 |
| `get_themes()` | 获取主题列表 |
| `stop_agent()` | 停止 Agent 执行 |

### 事件推送

`WebChatBridge` 通过 `evaluate_js("window.ChatApp.handleEvent(...)")` 推送事件：

- 用户/助手消息
- 流式 token
- 工具调用卡片
- 审批请求
- 运行状态变更

## 页面布局

```
┌─────────────────────────────────────────────────────┐
│  侧边栏          │  主聊天区                         │
│  · 会话列表      │  · 消息气泡（用户/助手/工具）      │
│  · 新建会话      │  · Markdown 渲染（marked.js）     │
│  · 设置入口      │  · 工具调用卡片（可折叠）          │
│                  │  · HITL 审批 UI                   │
├──────────────────┼───────────────────────────────────┤
│                  │  Composer 输入区                   │
│                  │  · 文本框 + 发送 + 停止             │
│                  │  · 斜杠命令菜单                    │
│                  │  · 附件（图片/文件）               │
│                  │  · 语音输入按钮                    │
├──────────────────┴───────────────────────────────────┤
│  万年历（可展开）                                     │
└─────────────────────────────────────────────────────┘
```

## 主题系统

- 23 套预设主题 JSON 位于 `themes/` 目录
- `src/ui/theme_loader.py` 加载主题并转为 CSS 变量
- 前端 `app.js` 应用主题到页面
- 用户偏好在 `data/user_settings.yaml` 中持久化

## 字体

- 使用 LXGW 文楷（霞鹜文楷）作为聊天字体
- 字体文件位于 `web/fonts/lxgwwenkaigb-regular/`
- `web/css/fonts-lxgw.css` 定义 @font-face

## 设置面板

Web 模态窗口提供：

- LLM Provider 选择与 API Key 配置
- 模型参数（温度、超时等）
- 主题切换
- Skill 目录配置
- 任务 owner 设置

## 遗留 CTk 组件

以下 CustomTkinter 组件仍存在于代码库，但**不是当前主 UI**：

| 文件 | 状态 |
|------|------|
| `src/ui/chat_panel.py` | 遗留聊天面板 |
| `src/ui/settings_dialog.py` | 遗留设置对话框 |
| `src/ui/knowledge_dialog.py` | 遗留知识库对话框 |
| `src/ui/confirm_dialog.py` | 遗留确认对话框 |
| `src/ui/bubble_text.py` | 遗留气泡文本组件 |

设置与知识库管理已迁移到 Web 模态窗口。

## 会话管理

- `src/ui/session_store.py` 管理会话 CRUD
- 存储：`data/sessions.db`
- 每条消息以 JSON 事件序列持久化，支持历史回放
