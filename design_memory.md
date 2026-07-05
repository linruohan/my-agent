# my-agent 记忆机制设计文档

## 文档信息

| 项目 | 内容 |
|---|---|
| 标题 | my-agent 记忆机制设计 |
| 参考文档 | Claude Code 系列05：记忆全景——从 Session 到 Memory 的六层持久化体系 |
| 版本 | v1.0 |
| 创建日期 | 2026-07-05 |

---

## 一、设计目标

参考 Claude Code 的六层持久化体系，构建 my-agent 的分层记忆系统，实现：

1. **跨项目共享与项目专属分离**：全局配置/记忆跨项目共享，项目配置/记忆专属定制
2. **上下文效率优化**：索引+主题结构，降低 token 消耗
3. **行为规则强约束力**：记忆提权协议，将行为规则提升到指导层
4. **团队协作支持**：项目级配置可提交 git，个人配置 gitignored

---

## 二、六层架构映射

| 层级 | Claude Code 概念 | my-agent 实现 | 状态 |
|------|------------------|--------------|------|
| **L1** | Settings（强制配置） | 全局/项目/本地 settings.json 分层合并 | 待实现 |
| **L2** | CLAUDE.md + Rules（指导层） | CLAUDE.md + rules/ 目录，支持路径范围加载 | 待实现 |
| **L3** | Auto Memory（记忆层） | MEMORY.md（索引）+ memory/（主题文件）+ 提权协议 | 核心增强 |
| **L4** | Session Transcripts（会话层） | SessionStore（数据库） | ✅ 已完善 |
| **L5** | Skills/Agents/MCP（扩展层） | src/ui/skill/ + src/tools/ | ✅ 已完善 |
| **L6** | App State（状态层） | user_settings.yaml + secrets.json | ✅ 已完善 |

---

## 三、目录结构

### 3.1 全局目录：`~/.my-agent/`

**路径**：Windows 上为 `C:\Users\<用户名>\.my-agent\`，存储跨项目共享的全局配置和记忆。

```
~/.my-agent/
├── settings.json              # 全局配置文件（用户级，跨项目生效）
├── USER.md                    # 全局用户画像（跨项目共享）
├── MEMORY.md                  # 全局记忆索引（跨项目共享的知识）
├── memory/                    # 全局主题文件目录
│   ├── user-preferences.md    # 用户偏好主题
│   ├── tech-stack.md          # 技术栈偏好
│   └── reference-links.md     # 外部引用链接
├── rules/                     # 全局规则目录
│   ├── behavior.md            # 通用行为规则
│   ├── security.md            # 安全规则
│   └── coding-style.md        # 编码风格规则
├── skills/                    # 全局 Skills
├── commands/                  # 全局 Commands
└── cache/                     # 全局缓存
    └── embeddings/            # Embedding 缓存
```

### 3.2 项目目录：`.my-agent/`

**路径**：项目根目录下，存储项目专属配置，支持团队共享。

```
<项目根>/.my-agent/
├── settings.json              # 项目级配置（团队共享，git）
├── settings.local.json        # 本地级配置（个人覆盖，gitignored）
├── CLAUDE.md                  # 项目级指导文件（团队共享，始终加载）
├── CLAUDE.local.md            # 本地级指导文件（个人覆盖，gitignored）
├── USER.md                    # 项目级用户画像
├── MEMORY.md                  # 项目级记忆索引
├── memory/                    # 项目主题文件目录
│   ├── project-context.md     # 项目上下文主题
│   ├── feedback-rules.md      # 用户反馈规则主题
│   └── domain-knowledge.md    # 领域知识主题
├── rules/                     # 项目规则目录
│   ├── project-behavior.md    # 项目行为规则（始终加载）
│   ├── api-conventions.md     # API 开发规范（paths: src/api/**）
│   └── testing-guidelines.md  # 测试规范（paths: tests/**）
├── rules.local/               # 本地规则目录（gitignored）
├── agents/                    # 项目级 Subagent 定义
├── skills/                    # 项目级 Skills
└── mcp.json                   # 项目级 MCP 配置
```

### 3.3 运行时数据目录：`data/`

```
data/
├── workspace/
│   ├── knowledge/             # RAG 知识库文件（保留）
│   ├── skills/                # 生成的 Skill 文件（保留）
│   └── browser_screenshots/   # 浏览器截图（保留）
├── vectorstore/               # FAISS 向量索引（保留）
├── checkpoints/               # 数据库文件（保留）
└── app.db                     # 主数据库（保留）
```

---

## 四、加载顺序与优先级

### 4.1 配置文件加载顺序（优先级从低到高）

| 优先级 | 范围 | 文件路径 | 共享范围 |
|--------|------|---------|---------|
| 最低 | 系统级（可选） | `C:\ProgramData\my-agent\settings.json` | 所有用户 |
| 低 | 全局级 | `~/.my-agent/settings.json` | 仅自己 |
| 中 | 项目级 | `.my-agent/settings.json` | 团队（git） |
| 最高 | 本地级 | `.my-agent/settings.local.json` | 仅自己（gitignored） |

**合并规则**：
- 数组类型（如 `permissions.allow`）：跨层合并
- 标量类型（如 `model`、`theme`）：取最具体的值

### 4.2 指导文件（CLAUDE.md）加载顺序

```
系统级 → 全局级 → 项目级 → 本地级 → 嵌套级
```

| 优先级 | 范围 | 文件路径 | 特点 |
|--------|------|---------|------|
| 最低 | 系统级 | `C:\ProgramData\my-agent\CLAUDE.md` | 不可排除 |
| 低 | 全局级 | `~/.my-agent/CLAUDE.md` | 所有项目生效 |
| 中 | 项目级 | `.my-agent/CLAUDE.md` | 团队共享（git） |
| 高 | 本地级 | `.my-agent/CLAUDE.local.md` | 个人覆盖（gitignored） |
| 动态 | 嵌套级 | `<subdir>/.my-agent/CLAUDE.md` | 子目录特定，按需加载 |

**关键机制**：
- 从当前工作目录向上遍历，每层加载 `CLAUDE.md` + `CLAUDE.local.md`
- 所有文件全量拼接，类似 CSS 层叠，冲突时"后出现的优先"
- 项目根目录的 `CLAUDE.md` 在 Context 压缩后仍保留；嵌套的不保留

### 4.3 记忆文件加载顺序

| 范围 | 文件路径 | 加载方式 |
|------|---------|---------|
| 全局 | `~/.my-agent/MEMORY.md` | 索引始终加载，主题按需读取 |
| 项目 | `.my-agent/MEMORY.md` | 索引始终加载，主题按需读取 |

**合并策略**：
- 索引文件：全局 + 项目拼接（全局在前）
- 主题文件：优先项目级，不存在时查找全局级
- 用户画像：全局 USER.md + 项目 USER.md 拼接

### 4.4 Rules 目录加载顺序

| 范围 | 文件路径 | 加载方式 |
|------|---------|---------|
| 全局 | `~/.my-agent/rules/*.md` | 启动时加载（无 paths）或按需加载（有 paths） |
| 项目 | `.my-agent/rules/*.md` | 启动时加载（无 paths）或按需加载（有 paths） |
| 项目本地 | `.my-agent/rules.local/*.md` | 同 rules，但 gitignored |

**优先级**：项目 Rules > 全局 Rules

---

## 五、核心设计

### 5.1 MEMORY.md（索引文件）格式

```markdown
# Agent 记忆索引

## 主题列表
- **user-preferences**（用户偏好）：用户是 AI 工程师，偏好架构约束
- **project-context**（项目上下文）：当前项目是个人助理 Agent，使用 Python + LangChain
- **feedback-rules**（反馈规则）：用户要求不要在测试中 mock 数据库
- **reference-links**（引用链接）：bugs 在 Linear INGEST 项目跟踪

## 统计信息
- 最后更新：2026-07-05 21:00:00
- 主题数量：4
- 总条目数：23

## 重要提醒
- 行为规则（"必须"、"禁止"）已提权到 .my-agent/rules/
```

### 5.2 主题文件格式

```markdown
---
type: feedback
created: 2026-07-01
updated: 2026-07-05
tags: [testing, database]
---

# 用户反馈规则

## 2026-07-05
- 不要在测试中 mock 数据库，使用真实数据库连接
- 测试数据应使用临时表，测试后自动清理

## 2026-07-03
- API 响应时间超过 3s 需要优化
```

### 5.3 记忆类型定义

| 类型 | frontmatter `type:` | 用途 | 存储位置 |
|------|---------------------|------|---------|
| `user` | 用户角色、偏好、知识背景 | USER.md + 主题文件 | 记忆层 |
| `feedback` | 用户对工作方式的纠正或确认 | MEMORY.md + 主题文件，规则提权 | 记忆层/指导层 |
| `project` | 项目进展、目标、截止日期 | MEMORY.md + 主题文件 | 记忆层 |
| `reference` | 外部系统的指针 | MEMORY.md + 主题文件 | 记忆层 |

### 5.4 Rules 文件格式

```markdown
---
paths: src/api/**              # 仅当读到 src/api/ 下的文件时加载
priority: high                 # high/medium/low
---

# API 开发规范
- 必须使用 RESTful 风格
- 接口返回统一 JSON 格式：{ "code": 0, "data": {}, "msg": "" }
- 错误码定义见 docs/api-error-codes.md
```

### 5.5 记忆提权协议

**核心问题**：行为规则存储在 Memory 中时，系统指令 framing 是"可能相关"，约束力弱。

**解决方案**：自动将行为规则提升到指导层。

**提权流程**：
```
用户反馈 → LLM 分类判断 → 存储位置
    │           │              │
    ├─ background（背景知识）──→ MEMORY.md + 主题文件
    │           │
    ├─ rule（行为规则）────────→ .my-agent/rules/（强约束力）
    │           │
    └─ critical（绝对禁止）────→ settings.json（强制约束）
```

**提权触发条件**：
1. 用户反馈包含"必须"、"不要"、"禁止"等指令性词汇
2. Memory 中的行为规则被违反过一次
3. 用户明确说"绝对不要"、"永远禁止"

---

## 六、上下文占用控制

| 内容 | 建议上限 | 说明 |
|------|---------|------|
| MEMORY.md（索引） | 2500 字符 | 始终加载 |
| USER.md | 3500 字符 | 始终加载 |
| CLAUDE.md | 2000 字符 | 始终加载 |
| Rules（无 paths） | 2000 字符 | 始终加载 |
| Rules（有 paths） | 按需 | 匹配时加载，压缩后丢失 |
| 主题文件 | 按需 | Claude 主动读取 |

---

## 七、模块划分与文件清单

### 7.1 新增文件

| 文件路径 | 功能说明 |
|---------|---------|
| `src/infra/paths.py`（新增函数） | 全局目录和项目目录路径解析 |
| `src/memory/rules_loader.py` | Rules 目录加载器，支持多层级加载 |
| `src/memory/memory_index.py` | 记忆索引管理，支持全局+项目合并 |
| `src/memory/memory_promotion.py` | 记忆提权协议，分类判断与提权 |
| `src/tools/memory/topic_tools.py` | 主题文件读取工具（供 Claude 调用） |
| `~/.my-agent/settings.json` | 全局配置模板 |
| `~/.my-agent/USER.md` | 全局用户画像模板 |
| `~/.my-agent/MEMORY.md` | 全局记忆索引模板 |
| `~/.my-agent/rules/behavior.md` | 全局行为规则模板 |
| `.my-agent/settings.json` | 项目配置模板 |
| `.my-agent/CLAUDE.md` | 项目指导文件模板 |
| `.my-agent/USER.md` | 项目用户画像模板 |
| `.my-agent/MEMORY.md` | 项目记忆索引模板 |
| `.my-agent/rules/project-behavior.md` | 项目行为规则模板 |

### 7.2 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `src/infra/config.py` | 新增多层级配置合并逻辑 |
| `src/memory/context_files.py` | 修改为支持全局+项目级记忆加载 |
| `src/tools/memory/tools.py` | 更新支持多层级记忆读写 |

---

## 八、实施计划

### Phase 1：基础架构（1-2天）
- 实现路径管理扩展（`src/infra/paths.py`）
- 实现配置分层合并逻辑（`src/infra/config.py`）
- 创建 Rules 目录结构和加载器（`src/memory/rules_loader.py`）

### Phase 2：记忆层重构（2-3天）
- 实现记忆索引管理（`src/memory/memory_index.py`）
- 创建主题文件目录和读写工具
- 更新 MEMORY.md 格式为索引结构
- 修改 `build_memory_prompt_block()` 支持规则注入

### Phase 3：记忆提权协议（1-2天）
- 实现分类判断逻辑（`src/memory/memory_promotion.py`）
- 集成到学习闭环流程
- 实现行为规则自动写入 Rules 目录

### Phase 4：测试与优化（1天）
- 编写单元测试
- 验证上下文占用优化效果
- 测试记忆提权流程

---

## 九、预期效果

| 指标 | 当前状态 | 优化后 |
|------|---------|--------|
| MEMORY 上下文占用 | ~4500 字符（全量） | ~2500 字符（仅索引） |
| 行为规则约束力 | 弱（参考式 framing） | 强（命令式 framing） |
| 记忆检索效率 | 线性搜索 | 主题索引 + 语义检索 |
| 配置灵活性 | 单一文件 | 分层覆盖，团队共享 |

---

## 十、风险与注意事项

1. **向后兼容性**：现有 `data/workspace/MEMORY.md` 需要平滑迁移到 `.my-agent/MEMORY.md`
2. **Context 压缩**：确保 Rules 在压缩后能正确重新注入
3. **分类准确性**：LLM 分类判断可能出错，需要人工复核机制
4. **存储大小**：主题文件可能无限增长，需要定期清理策略
5. **性能**：多层级加载可能增加启动时间，需要缓存机制

---

## 十一、参考资料

- Claude Code 系列05：记忆全景——从 Session 到 Memory 的六层持久化体系
- [项目现有记忆模块](src/memory/)
- [项目现有配置模块](src/infra/config.py)
- [项目现有路径模块](src/infra/paths.py)
