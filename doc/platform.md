# Windows 平台能力

my-agent 深度集成 Windows 平台特性，包括 OCR、系统通知等。部分能力在非 Windows 平台上不可用或功能受限。

## 语音识别

**现状：未实现（规划中）。**

- `pyproject.toml` 仍声明 winrt SpeechRecognition 依赖，供后续接入
- Web 前端 Composer 区保留麦克风相关样式，但无可用桥接
- 文档旧路径 `src/ui/speech/` **不存在**；实现前请勿按此路径引用

计划能力：Windows Runtime `SpeechRecognition` → 设置开关 → Composer 麦克风填入输入框。

## OCR 文字识别

### 源码

```
src/ui/ocr/
└── (Windows OCR 实现)

src/ui/ocr_win.py     # Windows OCR 入口
src/ui/ocr_worker.py  # 后台 OCR 工作线程
```

### 两种 OCR 后端

| 后端 | 依赖 | 说明 |
|------|------|------|
| Windows OCR | winrt-Windows.Media.Ocr | 默认，系统内置 |
| PaddleOCR | paddleocr, paddlepaddle | 可选，精度更高 |

安装可选 OCR：

```bash
pip install -e ".[input]"
```

### 触发方式

1. **附件 OCR** — 发送含图片的消息，自动识别文字
2. **斜杠命令** — `/ocr` 触发最近一次图片附件的 OCR
3. **意图识别** — 消息含「识别」「OCR」等关键词

### 依赖

```
winrt-Windows.Media.Ocr
winrt-Windows.Graphics.Imaging
winrt-Windows.Storage
winrt-Windows.Storage.Streams
```

## 系统通知

### 源码

```
src/tools/task/notify.py  # TaskReminderService
```

### 技术

- 使用 `win11toast` 发送 Windows Toast 通知
- 用于任务到期提醒

### 依赖

```
win11toast
pywin32
```

## 剪贴板

### 源码

`src/ui/` 中的剪贴板相关工具

- 支持从剪贴板粘贴图片到 Composer
- 支持复制助手回复到剪贴板

## 打开本地文件

### 源码

`src/ui/open_local.py`

- 聊天中的本地文件链接可点击打开
- 调用系统默认程序打开文件

## 平台依赖汇总

以下依赖仅在 Windows 平台安装（`sys_platform == 'win32'`）：

| 包 | 用途 |
|----|------|
| winrt-runtime | Windows Runtime 基础 |
| winrt-Windows.Media.SpeechRecognition | 语音识别（规划中） |
| winrt-Windows.Media.Ocr | OCR |
| winrt-Windows.Graphics.Imaging | 图像处理 |
| winrt-Windows.Storage | 文件存储 |
| winrt-Windows.Globalization | 国际化 |
| winrt-Windows.Foundation | 基础类型 |
| pywin32 | COM 接口 |
| win11toast | Toast 通知 |

## 跨平台说明

- **核心 Agent 功能**（对话、工具调用、文件操作）在 macOS/Linux 上可运行
- **UI**（pywebview）跨平台
- **OCR、Toast 通知** 仅 Windows；语音尚未接线
- 建议在 Windows 10/11 上使用以获得完整体验
