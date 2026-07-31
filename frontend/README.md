# my-agent React UI

Vite + React + TypeScript + Tailwind 前端，通过 pywebview `js_api` 对接现有 Python Agent。

## 开发

```bash
cd frontend
npm install
npm run build   # 输出到 ../web/dist
```

启动应用（优先加载 `web/dist`）：

```bash
# 项目根目录
python main.py
```

强制旧版 UI：

```bash
# PowerShell
$env:AGENT_UI="legacy"; python main.py
```

强制新版（若未 build 会报错）：

```bash
$env:AGENT_UI="react"; python main.py
```

浏览器热更新调试（无 pywebview API，仅看布局）：

```bash
npm run dev
```

## 目录

- `src/bridge/` — 与 `src/ui/api` / WebChatBridge 对齐的类型与 API 封装
- `src/stores/` — UI 状态（会话消息、主题、HITL）
- `src/components/` — 侧栏 / 聊天 / Composer / 审批
- `src/styles/tokens.css` — 设计令牌（承接 Python 注入的主题 CSS 变量）
