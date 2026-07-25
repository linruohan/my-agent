# my-agent 未完善与可优化清单

> 审查日期：2026-07-25（刷新）  
> 范围：`src/`、`web/`、`doc/`、设计文档、测试、工程配置、工作区卫生  
> 说明：主路径（Agent / 任务 / 搜索 / 记忆 / `app.db` / Gateway / 热重载）完整度较高；下文聚焦**仍开放**项。  
> 历史已落地项见文末「已完成归档」。

---

## 总评

项目不是大面积 stub，而是早期产品态（`0.1.0`）：核心链路可用，缺口集中在 **Phase 2 产品能力**、**记忆抽取与主对话争 LLM**、**安全硬化**、**测试/文档/仓库卫生**。

| 维度 | 状态 |
|------|------|
| Agent / 工具 / UI | 主路径完整 |
| 记忆主链路 | 已闭环；fork 抽取未做 |
| Gateway | 功能可用；默认 token 空、深度集成可扩 |
| 统一 `app.db` | 迁移逻辑已完成；`*.migrated` 污染 git |
| Phase 2 | 语音、托盘、邮件、RAG MMR 未做 |

---

## 一、优先行动（当前 Top 5）

1. **Gateway 启用时强制非空 `http_token`**（`config/app.yaml` 默认 `""`）
2. **记忆抽取与主对话解耦**（轻量模型 / 队列 / 真正 fork，对应原 A15）
3. **`.gitignore` 忽略 `data/*.migrated*`**（及 `-shm`/`-wal`），清理工作区脏文件
4. **清理 MagicMock 污染记忆**（`.my-agent/MEMORY.md` 中有测试噪声条目）
5. **补关键路径测试**：memory extract 端到端、learning 全流程 mock、`agent_sync` cron agent

---

## 二、未完善 / 半成品（仍开放）

### P0 — 安全 / 体验成本

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| S1 | `config/app.yaml` → `gateway.http_token` | 默认空字符串；启用 HTTP 时可无鉴权 | 启用 gateway/http 时校验非空；启动告警 |
| S2 | `src/tools/code/sandbox.py` | 正则拦 `_BLOCKED_IMPORTS`，非强隔离；会话 pickle 落盘 | 文档标明信任边界；会话 TTL/体积上限；评估 AST/子进程更严策略 |
| A15 | `runner._trigger_memory_extraction` + `memory_writer` | 同 LLM 后台线程抽取，与主对话争模型；`design_memory.md` 的 `runForkedAgent` / prompt cache 未实现 | 队列化 + 轻量模型，或真 fork + cache 复用 |

### P1 — 产品能力缺口

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| P1 | 语音输入 | `doc/platform.md` / `doc/ui.md`：未实现；依赖在 optional `.[speech]`；前端仅有 `pulse-mic` CSS，无桥接 | 做桥接，或从 UI 去掉 mic 样式避免假入口 |
| P2 | 系统托盘 | 设计文档标 Phase 2 | 按需排期 |
| P3 | 邮件 / Notion / 飞书 | `send_email` 等 Phase 2 / out-of-scope；无实现 | 保持 out-of-scope 或单独立项 |
| P4 | RAG MMR | `src/memory/rag.py` 仅 top-k；设计文档标 Phase 2 | 需要去重多样性时再加 |
| A8 | Auto/Team 记忆 | Team 有 `team_memory_enabled`；Auto 启动摘要注入仍可选 | 启动时可选注入 Auto 摘要 |

### P2 — 体验 / 数据一致

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| D1 | 日历存储 | `data/workspace/calendar.json`；任务/笔记已在 `app.db` | 迁入 SQLite，统一事务与查询 |
| D2 | 宽 `except Exception` | `turns.py`、`memory_reader`、`search_cache`、`file/search` 等仍偏宽（部分已打 debug） | 继续收窄类型、关键路径打结构化日志 |
| D3 | 兼容 shim | `ocr_win.py`、`task_store.py`、`search.py` 等 20+ re-export | 冻结后逐步删除旧导入路径 |
| D4 | `.my-agent/CLAUDE.md` | 仍是模板占位「（项目目标、技术栈…）」 | 填入真实项目概述与约定 |
| D5 | 记忆噪声 | `MEMORY.md` 含 `feedback-magicmock-...` | 修 learning 写入过滤；删除脏记忆文件 |

源码中几乎无真正的 `TODO`/`FIXME`；`NotImplementedError` 仅见于 `gateway/base.py` 抽象方法（非 stub）。

---

## 三、可优化点（仍开放）

### 性能

| 位置 | 现状 | 建议 |
|------|------|------|
| 记忆抽取 | 与主对话同步抢同一 LLM | 见 A15 |
| 大文件 | `weather/render.py`、`skill/runner.py`、`controller/turns.py`、`settings.py` 等偏大 | 按职责继续拆模块 |
| 代码沙箱会话 | `.pkl` 会话可膨胀 | TTL、最大体积、过期清理 |

### 架构

| 位置 | 现状 | 建议 |
|------|------|------|
| 日历 vs 任务/笔记 | JSON vs SQLite 双介质 | 统一到 `app.db` |
| 双轨记忆配置 | 已互斥（`memory_extraction` vs `auto_update_memory`） | 保持配置纪律，文档强调互斥 |
| API Key 明文 | `data/secrets.json` fallback（已 gitignore） | 文档强调权限与备份；避免进备份包 |

### 工程 / DX

| 项 | 现状 | 建议 |
|----|------|------|
| `*.migrated` | 迁移归档未进 `.gitignore`，git status 大量 `??` / `D` | 忽略 `data/*.migrated*`、`data/*-shm`、`data/*-wal`（非 app.db 已 ignore 的） |
| `data/app.db` | 若曾被 track，本地仍可能 `M` | 确认 `git rm --cached`；保持 ignore |
| mypy | 仅 `src/infra/config.py`、`paths.py` | 扩大到 `database/`、`gateway/config`、`memory/service` |
| CI | Ubuntu 跳过 Windows/OCR/browser；无 macOS；无 browser 独立 job | 可选：定时 Playwright job |
| 无 CHANGELOG | — | 发版时补简版 |
| `yh.md` vs `doc/` | 审查清单与正式文档双源 | 长期以 `doc/` 为准，本文件仅作 backlog |

### 安全（汇总）

| 严重度 | 项 |
|--------|----|
| 高 | Gateway `http_token` 默认可为空 |
| 中 | 沙箱正则拦 import，可被绕过 |
| 中 | secrets 明文本地文件 |
| 低 | Skill `subprocess.run` 依赖 Skill 来源可信 |

---

## 四、文档与实现不一致（仍开放）

| 文档 | 问题 | 严重度 |
|------|------|--------|
| `design_memory.md` | 仍写 `runForkedAgent`；L1/L2「待实现」状态表过时 | 中 |
| `doc/ui.md` | 语音未实现；路径说明需与 `web/js/core|features/` 保持同步 | 中 |
| `个人助理Agent设计文档.md` | 结构树仍含 `email.py` 等未实现节点；缺 `gateway/`、`automation/` | 低 |
| `doc/platform.md` | OCR 路径注释与 `src/ui/ocr/` + 兼容入口略有漂移 | 低 |

已对齐项：CustomTkinter→pywebview、FAISS、`app.db`、critical→`settings.local.json`、语音「未实现」标注等。

---

## 五、测试缺口（仍开放）

### 覆盖较好

LLM 工厂、意图路由、任务、搜索缓存、RAG、记忆系统、DB 迁移、OCR（Windows）、日历冲突、Gateway ingest / deliver_reply / HITL（mock）。

### 明显缺口

| 模块 | 缺口 |
|------|------|
| `runner._trigger_memory_extraction` | 缺端到端集成测试 |
| `learning.maybe_learn_from_turn` | 仅 dedupe；缺 LLM mock 全流程（且曾写出 MagicMock 记忆） |
| `automation/agent_sync.py` | `action_type=agent` 覆盖薄 |
| `web_bridge` / `controller/gateway` | 缺专用测试 |
| Gateway bots | 有 mock，无真实网络 E2E |
| `browser_integration` | marker 已定义，CI 默认跳过 |

约 62 个 `test_*.py`，相对 `src/` ~201 个模块，覆盖面可继续加深而非从零开始。

---

## 六、工作区与迁移卫生

**结论：迁移逻辑已完成，不是半成品；脏文件是归档产物 + ignore 缺口。**

- `migrate_legacy_databases()` 将旧库合并进 `app.db` 后重命名为 `*.db.migrated`（含 wal/shm）
- 启动 `ensure_database()` 会触发；另有 todos.json、memory v1→v2、search_cache 等脚本
- 当前现象：`?? data/*.migrated*`、`D data/*.db`、可能的 `M data/app.db` / `M .my-agent/MEMORY.md`

**建议：**

```gitignore
data/*.migrated
data/*.migrated-shm
data/*.migrated-wal
data/*.db.migrated
data/*.db.migrated-shm
data/*.db.migrated-wal
```

确认 `app.db` 数据完整后，本地可删除旧 `*.migrated` 备份。

---

## 七、建议排期（针对仍开放项）

| 阶段 | 内容 |
|------|------|
| Sprint A（安全/卫生） | S1 http_token 校验；gitignore `*.migrated*`；清理 MagicMock 记忆；learning 写入防 mock |
| Sprint B（性能/记忆） | A15 抽取队列或轻量模型；extract / learning 测试；同步 `design_memory.md` 状态 |
| Sprint C（产品决策） | 语音：做 or 去 UI；托盘/邮件按需；日历迁 SQLite |
| 持续 | 收窄 except、拆大文件、扩大 mypy、删 shim、RAG MMR |

---

## 八、已完成归档（摘要，勿重复排期）

双轨记忆互斥、critical→`settings.local.json`、`load_merged_settings`、already_surfaced、验证提示、Speech 改 optional、日历冲突检测、Gateway HITL/webhook/忙时排队、Telegram→`PollingGateway`、Team flag、增量 DB 迁移、MemoryService 门面、记忆选择 TTL+预筛、extract 限流、任务 store 拆分、多盘符搜索失败提示、模型列表后端优先、节假日 JSON、`/reload` 热重载、ruff + 渐进 mypy、CI 跳过 browser_integration、文档 `app.db` 对齐等。

详情见本文件历史版本或 git 记录。

---

*本文件为 backlog；修复后请勾选/更新对应条目。正式行为说明以 `doc/` 为准。*
