# my-agent 未完善与可优化清单

> 审查日期：2026-07-25  
> 范围：`src/`、`web/`、`doc/`、设计文档、测试与工程配置  
> 说明：按优先级排列，便于排期；路径以仓库根目录为准。  
> **2026-07-25 已落地（两轮）**：记忆统一 / critical / settings / 文档 / gitignore；  
> 以及 A11 日历冲突、A14 remote HITL `ask`、A18 增量迁移、A7 语音依赖可选化、Gateway mock 测试、宽 except 日志。

---

## 一、优先行动（Top 5）

1. ~~**统一记忆写入模型**~~ ✅
2. ~~**修复 critical 提权写 `config/app.yaml`**~~ ✅
3. ~~**接入 `load_merged_settings`**~~ ✅
4. ~~**同步文档**~~ ✅
5. ~~**补 Gateway / 记忆回归测试**~~ ✅（HTTP/Telegram ingest / deliver_reply / HITL 解析）

---

## 二、未完善 / 半成品

### P0 — 影响核心能力或数据一致性

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| A1 | ~~双轨记忆~~ ✅ | learning / `update_agent_memory` → 结构化文件；`memory_extraction` 与 `auto_update_memory` 互斥 | 已完成 |
| A2 | ~~`load_merged_settings` 未用~~ ✅ | critical / team flag / stale_days 已接入 | 已完成 |
| A3 | ~~critical 写 app.yaml~~ ✅ | 改为 `settings.local.json` | 已完成 |
| A4 | ~~硬编码时间戳~~ ✅ | `.last_write` + 限流 | 已完成 |
| A5 | ~~already_surfaced 失效~~ ✅ | `memory_session` 按 thread_id 持久 | 已完成 |
| A6 | ~~验证未接线~~ ✅ | 注入块附带 `build_verification_prompt` | 已完成 |
| A7 | ~~Speech 默认依赖~~ ✅ | 移至 optional `.[speech]`；文档已同步 | 后续实现桥接时可安装 extras |
| A8 | Auto/Team 注入 | Team 已受 `team_memory_enabled` 控制；Auto 走检索注入 | 可选：启动时摘要 Auto 进 prompt |

### P1 — 可用但有明显缺口

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| A9 | ~~设计文档多节点图~~ ✅ | 设计文档已注明「纯 ReAct + UI 意图路由」 | 已完成 |
| A10 | `个人助理Agent设计文档.md` | `send_email`、跨应用、**系统托盘**未实现 | Phase 2 / out-of-scope |
| A11 | ~~日历无冲突检测~~ ✅ | `find_calendar_conflicts` + 创建时提示 | 已完成 |
| A12 | Gateway 测试 | HTTP/Telegram ingest / deliver_reply 已补 mock | Discord/Slack 仍可加深；webhook 可选 |
| A13 | `src/gateway/telegram_bot.py` | 未继承 `PollingGateway`，与 Discord/Slack 不一致 | 统一基类或抽取公共鉴权/推送 |
| A14 | ~~远程 HITL 无交互~~ ✅ | `remote_hitl: ask` + `/approve`/`/reject`；忙时提示排队 | 已完成 |
| A15 | `design_memory.md` §6.1 | `runForkedAgent` / prompt cache 复用未实现；extract 与主对话同步抢同一 LLM | 后台轻量模型或队列化抽取 |
| A16 | ~~Team 无 flag~~ ✅ | `memory.team_memory_enabled` | 已完成 |
| A17 | 设计文档 §4.1 | `langgraph.store` 长期记忆未实现 | 实现 Store，或从设计文档删除 |
| A18 | ~~无增量迁移~~ ✅ | `app.db` 已存在时仍 `INSERT OR IGNORE` 合并并归档 | 已完成 |
| A19 | ~~learning 与 extract 并行~~ ✅ | `auto_update_memory: false` + 配置互斥默认 | 已完成 |

### P2 — 边缘 / 体验

| ID | 位置 | 现状 | 建议 |
|----|------|------|------|
| A20 | 根目录 `test_search.py` | 手动调试脚本（搜用户 home 下文件），非 pytest | 移入 `scripts/` 或删除 |
| A21 | `src/ui/input_intent.py` 等 | 多处 shim 重导出 | 收敛导入路径 |
| A22 | `web/js/features/holidays.js` | 节假日硬编码至约 2027 | 外部数据源或配置化 |
| A23 | `context_files.py` | 读取 `USER.md.local`（非设计路径） | 对齐 `CLAUDE.local.md` 体系或删除 |
| A24 | `src/gateway/base.py` | `NotImplementedError` 为抽象基类，非 stub | 文档说明即可 |

---

## 三、可优化点

### 性能

| 位置 | 现状 | 建议 |
|------|------|------|
| `src/agent/graph.py` 记忆选择 | 每轮用户消息可能触发 **LLM 记忆选择**（同主模型） | 小模型/规则预筛；缓存 query→memories |
| `runner.py` + `memory_writer.py` | 每轮结束 fire-and-forget 再调 LLM 抽取 | 限流（每 N 轮一次）或仅在有反馈信号时触发 |
| `src/tools/task/store.py`（约 680+ 行） | 单文件职责混合 | 拆分 CRUD / 提醒 / 迁移 |
| `src/tools/file/search.py` | 多盘符搜索；部分路径静默吞错 | 汇总失败盘符并反馈用户 |

### 架构

| 位置 | 现状 | 建议 |
|------|------|------|
| Memory 全链路 | 索引、扁平 MEMORY、结构化文件、learning 多入口 | 定义单一 `MemoryService` API |
| API 目录 | 实现在 `src/ui/api/`，无顶层 `src/api/` | 文档澄清；或按域拆包 |
| Gateway | Inbox 与 `app.db` 同库；HTTP 无 TLS | 部署文档补充 token、反向代理要求 |

### 体验

| 位置 | 现状 | 建议 |
|------|------|------|
| `web/js/core/layout.js` | 模型列表可能前端直连 Provider（CORS/密钥风险） | 默认走后端代理 |
| `src/ui/controller/turns.py` 等 | ~~宽 except 静默~~ ✅（turns/clipboard/link/file_dialog/browser 已打 debug） | 其余路径可继续收紧 |
| Gateway 忙时 | ~~无排队提示~~ ✅ | 已回复「请稍候」并重排队 |

### 工程

| 位置 | 现状 | 建议 |
|------|------|------|
| `pyproject.toml` | 无 ruff/mypy/black；`src/` 宽 `except` 较多 | 引入 linter 并渐进收紧 |
| CI | Linux 忽略 OCR；无 playwright install 专用 job | browser 测试加 setup 或默认 skip |
| `packaging/stage_release.py` | 仍列举旧分散库名 | 更新为 `app.db` 中心描述 |
| 配置热更新 | `app.yaml` 改完需重启 | 对标 Gateway `reload()` 做配置热加载 |

---

## 四、文档与实现不一致

| 文档 | 实现现状 | 严重度 |
|------|----------|--------|
| `个人助理Agent设计文档.md` — CustomTkinter | 实际为 **pywebview + web/**（`doc/architecture.md` 正确） | 高 |
| 同上 — SystemTray、ConfirmDialog | 合入 web HITL + controller | 中 |
| 同上 — chromadb、langgraph.store | 仅用 **FAISS + fastembed**，无 chromadb | 中 |
| 同上 — RAG MMR | `src/memory/rag.py` 无 MMR | 低 |
| `design_memory.md` L1/L2「待实现」 | 大量 CLAUDE 分层与合并逻辑已存在，状态表过时 | 中 |
| `design_memory.md` — critical→settings.json | ~~已改为 settings.local.json~~ ✅ | — |
| `doc/config-data.md`、`doc/README.md`、各 tools 文档 | ~~已统一为 app.db~~ ✅ | — |
| `doc/platform.md` — 语音模块路径 | ~~已标明未实现 + optional speech~~ ✅ | — |
| `doc/ui.md` — JS 路径、`voice.py` | 实际在 `web/js/core|features/`；语音未实现 | 中 |
| 设计文档项目结构 | 缺 `gateway/`、`automation/` 等；有未实现的 `email.py` | 低 |

---

## 五、测试与工程债

### 覆盖较好的区域

LLM 工厂、意图路由、任务解析/调度、搜索缓存、RAG、浏览器工具（mock）、Gateway inbox、记忆系统（`test_memory_system.py`）、数据库迁移、Hermes 阶段特性、OCR（Windows）。

### 明显缺口

| 模块 | 缺口 |
|------|------|
| `telegram_bot` / `discord_bot` / `slack_bot` / `http_server` | 无网络/mock 测试 |
| `gateway/service.py` → `deliver_reply` | 分片发送、outbound fallback 未测 |
| `runner._trigger_memory_extraction` | 无端到端集成测试 |
| `learning.maybe_learn_from_turn` | 仅 dedupe 单测，缺 LLM mock 全流程 |
| `memory_reader` × `graph` 注入 | 缺集成测试 |
| `automation/agent_sync.py` | cron agent 动作覆盖薄 |
| `web_bridge` / `controller/gateway` | 缺专用测试 |
| `memory_promotion` critical 写文件 | **无回归测试阻止写 app.yaml** |

### 其他工程债

| 项 | 说明 |
|----|------|
| `test_search.py` | 根目录临时脚本，应移出 |
| CI 矩阵 | Ubuntu 3.11/3.12 + Windows 3.12；无 macOS；Windows 跑全量含 OCR |
| `browser_integration` marker | 已定义，CI 无单独 job |
| Build | 仅 Windows 打包 workflow，无 Linux 打包 |
| `.gitignore` | 忽略了旧分散库，**未忽略 `data/app.db`**；`data/checkpoints/*.db-wal` 等易被误提交（当前 git status 可见） |

---

## 六、专题速览

### Gateway / 多通道

- 非 stub：`service.py`、`inbox.py`、`http_server.py`、三家 bot 均有轮询/WS 逻辑。
- 半成品：HTTP 入站 POST + 出站 GET 轮询；`remote_hitl` 无远程交互；架构不统一（Telegram）。

### Memory

- 已较完整：索引、rules 条件加载、@include、extract、find、promotion、格式校验。
- 未闭环：主动验证未接线、settings 合并未用、双轨写入、Auto/Team 未注入、learning 与 extract 可能重复。

### Automation

- Cron 生命周期、delivery（toast/session/gateway）有测试。
- `action_type=agent` 依赖运行时 graph，覆盖薄。

### UI

- 结构清晰：`web/js/core/` + `features/`。
- 需关注：宽 except、语音 UI 未接线、文档路径过时。

### 配置与数据

- 运行时统一库：`data/app.db`（`src/database/manager.py` / `paths.py`）。
- 文档与 packaging 仍部分停留在多库时代。
- `config/search.yaml` 已指向 `app.db`。

---

## 七、建议排期（参考）

| 阶段 | 内容 |
|------|------|
| Sprint 1 | A3 修复 critical 写入；`.gitignore` 补 `app.db`；文档数据库路径修正；A1 定方案（互斥或合并） |
| Sprint 2 | A1/A19 落地统一记忆；A2 接入或删除 settings 合并；A4 真实去重时间戳；A6 验证接线 |
| Sprint 3 | A7 语音决策；A14 remote HITL；Gateway mock 测试；设计文档与 `design_memory.md` 状态表同步 |
| 持续 | 宽 except 收紧、大文件拆分、记忆选择性能、日历冲突检测 |

---

*本文件由代码审查生成，后续修复时请勾选/更新对应条目。*
