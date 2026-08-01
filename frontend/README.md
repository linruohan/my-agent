# my-agent React UI

Vite + React + TypeScript + Tailwind 前端，通过 pywebview `js_api` 对接现有 Python Agent。

## 开发

```bash
cd frontend
npm install
npm run build   # 输出到 ../dist/web（构建产物，勿手改）
```

启动应用（优先加载 `dist/web`）：

```bash
python main.py
```

强制旧版 UI（`legacy/web`）：

```bash
$env:AGENT_UI="legacy"; python main.py
```

## 目录约定

| 路径 | 用途 |
|------|------|
| `frontend/` | React **源码**（在此修改） |
| `dist/web/` | `npm run build` **产物**（勿当源码改） |
| `legacy/web/` | 旧版 vanilla UI 归档 |
| `resources/themes/` | 主题 JSON |
