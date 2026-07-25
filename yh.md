# my-agent 未完善与可优化清单

> 审查日期：2026-07-25（刷新）  
> 本轮落地：2026-07-25 Sprint A + A15（http_token / gitignore / MagicMock 过滤 / 抽取队列）  
> 范围：`src/`、`web/`、`doc/`、设计文档、测试、工程配置  
> 说明：主路径完整度较高；下文聚焦**仍开放**项。历史已完成见文末归档。

---

## 总评

核心链路可用。本轮已闭合安全与卫生 Top 项；剩余主要是 **Phase 2 产品能力**、**日历存储统一**、**测试加深**、**文档漂移**。

| 维度 | 状态 |
|------|------|
| Agent / 工具 / UI | 主路径完整 |
| 记忆主链路 | 已闭环；抽取已队列化 + 可选专用 provider |
| Gateway | 功能可用；启用 HTTP 时强制非空 token ✅ |
| 统一 `app.db` | 迁移完成；`*.migrated` 已 ignore ✅ |
| Phase 2 | 语音、托盘、邮件、RAG MMR 未做 |

---

## 一、优先行动（当前 Top 5）

1. ~~Gateway 启用时强制非空 `http_token`~~ ✅
2. ~~记忆抽取与主对话解耦（队列 + 可选专用 provider）~~ ✅（真 fork / prompt cache 仍可选）
3. ~~`.gitignore` 忽略 `data/*.migrated*`~~ ✅
4. ~~清理 MagicMock 污染记忆 + 写入过滤~~ ✅
5. **补关键路径测试加深**：learning 全流程 mock 集成、`agent_sync` cron agent（抽取队列单测已补）

---

## 二、未完善 / 半成品（仍开放）

### P0 — 安全 / 体验成本

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| ~~S1~~ | ~~`gateway.http_token`~~ ✅ | 启用 HTTP 时空 token 拒启 + 服务端空 token 一律 401 | — |
| S2 | `src/tools/code/sandbox.py` | 正则拦 import，非强隔离；会话 pickle 落盘 | 文档标明信任边界；会话 TTL/体积上限 |
| ~~A15~~ | ~~记忆抽取争 LLM~~ ✅ | `schedule_memory_extraction` 单 worker + coalesce；`provider` 可配轻量模型 | 可选：真 `runForkedAgent` + prompt cache |

### P1 — 产品能力缺口

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| P1 | 语音输入 | 未实现；`.[speech]` optional；前端仅有 mic CSS | 做桥接，或去掉 mic 样式 |
| P2 | 系统托盘 | 设计文档标 Phase 2 | 按需排期 |
| P3 | 邮件 / Notion / 飞书 | Phase 2 / out-of-scope | 保持或单独立项 |
| P4 | RAG MMR | 仅 top-k | 需要去重多样性时再加 |
| A8 | Auto/Team 记忆 | Team 有 flag；Auto 启动摘要注入仍可选 | 启动时可选注入 Auto 摘要 |

### P2 — 体验 / 数据一致

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| D1 | 日历存储 | `calendar.json`；任务/笔记在 `app.db` | 迁入 SQLite |
| D2 | 宽 `except Exception` | 部分已打 debug，仍偏宽 | 继续收窄 + 结构化日志 |
| D3 | 兼容 shim | 20+ re-export | 冻结后逐步删除 |
| D4 | `.my-agent/CLAUDE.md` | 模板占位 | 填入真实概述 |
| ~~D5~~ | ~~记忆噪声~~ ✅ | 已删 MagicMock 文件并重建索引；写入路径拒绝 mock 串 | — |

---

## 三、可优化点（仍开放）

### 性能

| 位置 | 现状 | 建议 |
|------|------|------|
| ~~记忆抽取堆积~~ ✅ | 单 worker + coalesce；可选 `memory_extraction.provider` | 配置轻量 provider 进一步降本 |
| 大文件 | `weather/render.py`、`skill/runner.py`、`turns.py` 等 | 继续拆模块 |
| 代码沙箱会话 | `.pkl` 可膨胀 | TTL、最大体积、过期清理 |

### 架构 / 工程

| 项 | 现状 | 建议 |
|----|------|------|
| 日历 vs SQLite | 双介质 | 统一到 `app.db` |
| secrets 明文 | `data/secrets.json`（已 ignore） | 文档强调权限与备份 |
| mypy | 仅 `infra/config.py`、`paths.py` | 扩大到 database / gateway / memory |
| CI | 无 macOS；browser 默认跳过 | 可选定时 Playwright job |
| 无 CHANGELOG | — | 发版时补 |

### 安全（汇总）

| 严重度 | 项 |
|--------|----|
| ~~高~~ | ~~Gateway 空 token~~ ✅ 已强制 |
| 中 | 沙箱正则拦 import |
| 中 | secrets 明文本地文件 |
| 低 | Skill subprocess 依赖来源可信 |

---

## 四、文档与实现不一致（仍开放）

| 文档 | 问题 | 严重度 |
|------|------|--------|
| `design_memory.md` | 仍写 `runForkedAgent`；状态表过时（抽取已队列化） | 中 |
| `doc/ui.md` | 语音未实现 | 中 |
| `个人助理Agent设计文档.md` | 结构树含未实现 `email.py` | 低 |
| `doc/platform.md` | OCR 路径注释略有漂移 | 低 |

---

## 五、测试缺口（仍开放）

| 模块 | 缺口 |
|------|------|
| `learning.maybe_learn_from_turn` | 缺 LLM mock 全流程（已有 MagicMock 拒绝单测） |
| `automation/agent_sync.py` | `action_type=agent` 覆盖薄 |
| `web_bridge` / `controller/gateway` | 缺专用测试 |
| Gateway bots | 有 mock，无真实网络 E2E |
| `browser_integration` | CI 默认跳过 |

已补：`test_gateway_http_token.py`、`test_memory_extraction_queue.py`（含 coalesce / MagicMock 过滤）。

---

## 六、工作区与迁移卫生

- ~~`*.migrated` ignore~~ ✅ 已写入 `.gitignore`
- 本地仍可手动删除旧 `data/*.migrated*` 备份（确认 `app.db` 完整后）
- `data/app.db` 保持 ignore；勿提交运行时库

---

## 七、建议排期（针对仍开放项）

| 阶段 | 内容 |
|------|------|
| ~~Sprint A~~ ✅ | http_token、gitignore、MagicMock、抽取队列 |
| Sprint B | 沙箱 TTL；learning / agent_sync 测试；同步 `design_memory.md` |
| Sprint C | 语音决策；日历迁 SQLite；托盘/邮件按需 |
| 持续 | 收窄 except、拆大文件、扩大 mypy、删 shim |

---

## 八、已完成归档（摘要）

双轨记忆互斥、critical→`settings.local.json`、settings 合并注入、验证提示、Speech optional、日历冲突、Gateway HITL/webhook/忙时排队、Team flag、增量 DB 迁移、MemoryService、记忆选择 TTL+预筛、extract 限流、任务 store 拆分、多盘符搜索提示、模型列表后端优先、节假日 JSON、`/reload`、ruff + 渐进 mypy、CI 跳过 browser、文档 `app.db` 对齐、**http_token 强制**、**migrated ignore**、**MagicMock 过滤**、**抽取队列+可选 provider**。

---

*本文件为 backlog；修复后请勾选/更新。正式说明以 `doc/` 为准。*
