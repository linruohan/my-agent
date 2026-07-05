# my-agent 记忆机制设计文档

## 文档信息

| 项目 | 内容 |
|---|---|
| 标题 | my-agent 记忆机制设计 |
| 参考文档 | Claude Code 系列05：记忆全景——从 Session 到 Memory 的六层持久化体系 |
| 版本 | v2.0 |
| 创建日期 | 2026-07-05 |
| 上次更新 | 2026-07-05 |

---

## 一、设计目标

参考 Claude Code 的**两层架构**（静态声明式 + 动态学习式），构建 my-agent 的分层记忆系统，实现：

1. **跨项目共享与项目专属分离**：全局配置/记忆跨项目共享，项目配置/记忆专属定制
2. **上下文效率优化**：索引常驻 + 内容按需，降低 token 消耗
3. **行为规则强约束力**：记忆提权协议，将行为规则提升到指导层
4. **团队协作支持**：项目级配置可提交 git，个人配置 gitignored
5. **自动学习闭环**：后台代理抽取记忆，小模型做检索选择，时间感知防过时

---

## 二、两层架构总览

my-agent 的记忆机制是**两条独立的线**，并行工作：

| 层级 | 本质 | 解决问题 | 类比 |
|------|------|---------|------|
| **静态层** | CLAUDE.md 体系（声明式指令） | 「我们怎么协作」「这个项目要遵守什么规则」——确定性的事 | 公司员工手册 |
| **动态层** | 自动记忆系统（学习式偏好） | 「我从跟你的互动中学到了什么」——不确定的事 | 自己的工作笔记 |

### 2.1 静态层：CLAUDE.md 的六个层级

按加载顺序从低到高：

| 优先级 | 层级 | 路径 | 可见范围 | 可修改性 |
|--------|------|------|---------|---------|
| 最低 | **Managed**（系统级） | `C:\ProgramData\my-agent\CLAUDE.md` | 所有用户 | 仅管理员 |
| 低 | **User**（全局级） | `~/.my-agent/CLAUDE.md` | 所有项目 | 仅自己 |
| 中 | **Project**（项目级） | `.my-agent/CLAUDE.md` | 团队共享 | 团队成员 |
| 高 | **Local**（本地级） | `.my-agent/CLAUDE.local.md` | 仅自己 | 仅自己（gitignored） |
| 动态 | **Auto**（自动记忆） | `.my-agent/memory/*.md` | 项目级 | 系统自动写入 |
| 动态 | **Team**（团队记忆） | `.my-agent/memory/team/*.md` | 团队共享 | 系统自动写入（需开启） |
| 动态 | **Nested**（嵌套级） | `<subdir>/.my-agent/CLAUDE.md` | 子目录特定 | 团队成员 |

**加载规则**：六层是**叠加关系**不是覆盖关系，启动时全部拼接进 system prompt，后加载的优先。

**嵌套级加载机制**：从当前工作目录向上遍历，每层加载 `CLAUDE.md` + `CLAUDE.local.md`；项目根目录的 `CLAUDE.md` 在 Context 压缩后仍保留，嵌套级按需加载。

### 2.2 动态层：自动记忆系统

动态层是 my-agent 的真正灵魂，实现**自己学、自己写、自己用**的完整闭环：

```
写入端                    检索端
┌─────────────────┐      ┌─────────────────┐
│ extractMemories │      │ findRelevant    │
│ 后台代理抽取     │      │ Memories        │
│ 每轮对话结束触发 │      │ 小模型选top-5   │
└────────┬────────┘      └────────┬────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌─────────────────┐
│ MEMORY.md 索引  │◄─────│ 注入上下文      │
│ + memory/ 文件  │      │ + 老化警告      │
└─────────────────┘      └─────────────────┘
```

### 2.3 六层架构映射（完整）

| 层级 | Claude Code 概念 | my-agent 实现 | 状态 |
|------|------------------|--------------|------|
| **L1** | Settings（强制配置） | 全局/项目/本地 settings.json 分层合并 | 待实现 |
| **L2** | CLAUDE.md（指导层） | 六层叠加 + @include + 条件规则 | 待实现 |
| **L3** | Auto Memory（记忆层） | 四种类型 + 索引常驻 + 内容按需 | 核心增强 |
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
├── CLAUDE.md                  # 全局级指导文件（所有项目生效）
├── USER.md                    # 全局用户画像（跨项目共享）
├── MEMORY.md                  # 全局记忆索引（跨项目共享的知识）
├── memory/                    # 全局记忆文件目录（一记忆一文件）
│   ├── user-role.md           # 用户角色（type: user）
│   ├── tech-stack.md          # 技术栈偏好（type: user）
│   └── reference-links.md     # 外部引用链接（type: reference）
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

**记忆文件组织原则**：采用「一记忆一文件」模式，每个记忆文件独立存储，文件名采用 `{type}-{slug}.md` 格式，便于检索和管理。

```
<项目根>/.my-agent/
├── settings.json              # 项目级配置（团队共享，git）
├── settings.local.json        # 本地级配置（个人覆盖，gitignored）
├── CLAUDE.md                  # 项目级指导文件（团队共享，始终加载）
├── CLAUDE.local.md            # 本地级指导文件（个人覆盖，gitignored）
├── USER.md                    # 项目级用户画像
├── MEMORY.md                  # 项目级记忆索引
├── memory/                    # 项目记忆文件目录（一记忆一文件）
│   ├── project-freeze.md      # 项目合并冻结（type: project）
│   ├── feedback-no-mock.md    # 不要用mock测试（type: feedback）
│   ├── feedback-summary.md    # 用户不喜欢总结（type: feedback）
│   ├── reference-linear.md    # Linear bug追踪（type: reference）
│   └── team/                  # 团队共享记忆（需feature flag开启）
│       └── feedback-pr-style.md  # PR风格要求（团队共享）
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
Managed → User → Project → Local → Auto → Team → Nested
```

| 优先级 | 范围 | 文件路径 | 特点 |
|--------|------|---------|------|
| 最低 | Managed | `C:\ProgramData\my-agent\CLAUDE.md` | 不可排除，仅管理员可改 |
| 低 | User | `~/.my-agent/CLAUDE.md` | 所有项目生效 |
| 中 | Project | `.my-agent/CLAUDE.md` | 团队共享（git） |
| 高 | Local | `.my-agent/CLAUDE.local.md` | 个人覆盖（gitignored） |
| 动态 | Auto | `.my-agent/memory/*.md` | 系统自动写入 |
| 动态 | Team | `.my-agent/memory/team/*.md` | 团队共享（需开启） |
| 动态 | Nested | `<subdir>/.my-agent/CLAUDE.md` | 子目录特定，按需加载 |

**关键机制**：
- 所有文件全量拼接，类似 CSS 层叠，冲突时"后出现的优先"
- 项目根目录的 `CLAUDE.md` 在 Context 压缩后仍保留；Auto/Team 记忆按需注入
- 嵌套级：从当前工作目录向上遍历，每层加载 `CLAUDE.md` + `CLAUDE.local.md`，仅当编辑子目录文件时加载

### 4.3 @include 指令

支持在 CLAUDE.md 中引用其他文件，避免重复编写：

```markdown
@~/company/security-rules.md
@./.my-agent/rules/api-conventions.md
```

**解析规则**：
- `@~` 指向全局目录 `~/.my-agent/`
- `@./` 指向当前目录
- 循环引用检测：同一文件最多引用一次
- 路径遍历防护：禁止 `..` 跳出根目录

### 4.4 Rules 目录加载顺序

| 范围 | 文件路径 | 加载方式 |
|------|---------|---------|
| 全局 | `~/.my-agent/rules/*.md` | 启动时加载（无 paths）或按需加载（有 paths） |
| 项目 | `.my-agent/rules/*.md` | 启动时加载（无 paths）或按需加载（有 paths） |
| 项目本地 | `.my-agent/rules.local/*.md` | 同 rules，但 gitignored |

**条件加载**：Rules 文件 frontmatter 中可配置 `paths` 字段，仅当当前编辑文件路径匹配时才加载。

**优先级**：项目 Rules > 全局 Rules

---

## 五、核心设计

### 5.1 四种记忆类型（强制分类）

只允许四种类型，其他一律不许写：

| 类型 | frontmatter `type:` | 用途 | 强制结构 |
|------|---------------------|------|---------|
| **user** | 用户角色、偏好、知识背景 | 让回答因人而异 | 无强制结构 |
| **feedback** | 用户对工作方式的纠正或确认 | 决定下次行为对不对 | **规则本身 + Why + How to apply** |
| **project** | 项目进展、目标、截止日期 | 反映项目当前状态 | **事实/决定 + Why + How to apply** |
| **reference** | 外部系统的指针 | 知道去哪里找 | 无强制结构 |

**为什么要强制分类**：
- 自由文本无约束 = 垃圾堆，三个月后什么都查不准
- 强制类型逼 agent 在写之前先做「分类决策」，写下来的东西才有用

### 5.2 feedback 类型强制结构

`feedback` 类型的正文**必须**包含三段：

```markdown
---
name: 不要用 mock 数据库
description: 集成测试必须连真实数据库
type: feedback
created: 2026-07-05
updated: 2026-07-05
tags: [testing, database]
---

集成测试必须连真实数据库，不要用 mock。

**Why:** 上季度 mock 测试通过了但 prod 迁移挂了，导致线上事故
**How to apply:** 所有标了「集成测试」的 case 都适用；单元测试可以用 mock
```

**设计意图**：只记规则不记原因，遇到边界情况就抓瞎。加上 Why 和 How，agent 在边界情况下能自己判断「这个 case 该不该破例」。

### 5.3 project 类型特殊要求

除了强制结构，`project` 类型还有一个要求：**必须把相对日期转成绝对日期**。

| 用户输入 | 存储内容 |
|---------|---------|
| 「周四之前冻结」 | 「2026-03-05 之前冻结」 |
| 「下周上线」 | 「2026-07-13 之前上线」 |

**原因**：「周四」过几天就过期了，「2026-03-05」永远准确。

### 5.4 MEMORY.md（索引文件）格式

```markdown
# Agent 记忆索引

## 记忆清单
- **user-role.md**（用户角色）：后端工程师，新接触 React
- **feedback-no-mock.md**（行为偏好）：集成测试不要用 mock 数据库
- **project-freeze.md**（项目动态）：移动端 3 月 5 号开始合并冻结
- **reference-linear.md**（外部指针）：pipeline bug 都在 Linear INGEST 项目里追踪

## 统计信息
- 最后更新：2026-07-05 21:00:00
- 记忆数量：4

## 重要提醒
- 行为规则（"必须"、"禁止"）已提权到 .my-agent/rules/
- 记忆不是真理，使用前请主动验证
```

**双截断保险**：防止长行索引炸弹

| 限制项 | 阈值 | 说明 |
|--------|------|------|
| 行数 | 200 行 | 索引条目过多时截断 |
| 字节数 | 25,000 字节 | 单条索引过长时截断（极端情况：197KB < 200 行） |

**截断策略**：任一限制先触发即截断，追加警告：`[记忆索引已截断，部分内容未加载]`

### 5.5 记忆文件格式

每条记忆是一个独立的 `.md` 文件，frontmatter 是「身份证」：

```markdown
---
name: 不要用 mock 数据库
description: 集成测试必须连真实数据库，不要用 mock
type: feedback
created: 2026-07-05
updated: 2026-07-05
tags: [testing, database]
---

集成测试必须连真实数据库，不要用 mock。

**Why:** 上季度 mock 测试通过了但 prod 迁移挂了，导致线上事故
**How to apply:** 所有标了「集成测试」的 case 都适用；单元测试可以用 mock
```

**设计要点**：
- `name`：唯一标识，用于检索和去重
- `description`：一句话描述，**决定了能不能被检索到**，非常重要
- `type`：四种类型之一
- `created/updated`：时间戳，用于老化判断

### 5.6 「不该存什么」原则清单

跟「该存什么」同样重要的，是「不该存什么」：

| 禁止存储内容 | 原因 |
|-------------|------|
| 代码模式、架构、文件路径、项目结构 | `grep` / `CLAUDE.md` 就能得到，存了反而和实际状态不一致 |
| Git 历史和最近改动 | `git log` / `git blame` 是权威，记忆只会落后于真相 |
| 调试方案和修复方法 | fix 已经在代码里，commit 已经记录了上下文 |
| CLAUDE.md 里已经写过的内容 | 避免重复，浪费 token |
| 临时任务状态和当前对话上下文 | 不属于长期记忆 |

**核心原则**：**只记代码推不出来的东西**。代码是「活的」，记忆是「死的」。如果记忆说「`AuthService` 在某个具体路径第 42 行」，但代码已经重构了，这条记忆就变成了「权威的错误」，比没有记忆还糟糕。

---

## 六、自动记忆闭环

### 6.1 写入：extractMemories 后台代理

**触发时机**：每轮对话完整结束后（模型给出最终回复、没有任何 tool call），通过 `stopHook` 钩子触发。

**设计优势**：
- 主模型不分心：主任务专注回答，写入由后台代理完成
- 复用 prompt cache：不是从零启动新对话，而是「完美 fork 主对话」，复用已计算的 system prompt
- 成本低：只看对话历史，决定「这次有没有值得记的东西」

**抽取逻辑**：
1. 扫描本轮对话中用户的反馈、纠正、信息
2. 跟现有记忆比对（检测 `hasMemoryWritesSince`），过滤重复
3. 按四种类型分类，生成 frontmatter + 正文
4. 写入新记忆文件，更新 MEMORY.md 索引

### 6.2 检索：小模型选择器

**核心思路**：不用向量检索，让小模型做选择题。

**检索流程**：

```
当前用户问题
      │
      ▼
第一步：扫描所有记忆文件的 frontmatter（只读前30行）
      │
      ▼
第二步：把记忆标题清单拼成文本，发给 Sonnet
      │
      ▼
第三步：Sonnet 用 JSON schema 返回 top-5 文件名
```

**检索提示词关键约束**：
```
Only include memories that you are certain will be
helpful based on their name and description.
Be selective and discerning.
```

**过滤机制**：
- `alreadySurfaced` 过滤：上一轮已露脸的记忆，这次排除
- `recentTools` 过滤：最近用过的工具的「用法参考文档」排除，但「警告、坑点、已知问题」保留

**为什么用 Sonnet 不是向量检索**：
- Sonnet 的判断是自然语言判断，可解释性强
- 记忆相关性判错的代价远大于多花的 token
- 维护向量数据库的人力 + 算力 > Sonnet 做选择题的成本

### 6.3 注入：system-reminder 包裹 + 老化警告

**注入格式**：

```
<system-reminder>
This memory was saved 5 days ago. Verify it's still accurate before acting on it.

[记忆内容]
</system-reminder>
```

**老化警告规则**：

| 存储时间 | 警告级别 |
|---------|---------|
| 今天 / 昨天 | 不警告 |
| 2 天以前 | 主动加警告：「This memory was saved X days ago. Verify it's still accurate.」 |

**主动验证机制**：在 system prompt 中明确告诉模型：
- 如果记忆里写了文件路径，先检查文件是否存在
- 如果记忆里写了函数名或 flag，先 grep 一下
- 如果用户要照建议动手，先验证再说

**核心心法**：**记忆不是真理，是历史快照**。模型对待记忆的姿态应该像对待 git log，「这是过去发生的事」，不是「这是现在的状态」。

---

## 七、记忆提权协议

**核心问题**：行为规则存储在 Memory 中时，系统指令 framing 是"可能相关"，约束力弱。

**解决方案**：自动将行为规则提升到指导层。

**提权流程**：
```
用户反馈 → LLM 分类判断 → 存储位置
    │           │              │
    ├─ background（背景知识）──→ MEMORY.md + 记忆文件
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

## 八、上下文占用控制

| 内容 | 建议上限 | 说明 |
|------|---------|------|
| MEMORY.md（索引） | 2500 字符（200行 + 25KB） | 始终加载，双截断保险 |
| USER.md | 3500 字符 | 始终加载 |
| CLAUDE.md（六层叠加） | 3000 字符 | 始终加载 |
| Rules（无 paths） | 2000 字符 | 始终加载 |
| Rules（有 paths） | 按需 | 匹配时加载 |
| 记忆文件（已选中） | 约 5 条，总计 ~3000 字符 | 按需加载 |

---

## 九、模块划分与文件清单

### 9.1 新增文件

| 文件路径 | 功能说明 |
|---------|---------|
| `src/infra/paths.py`（新增函数） | 全局目录和项目目录路径解析 |
| `src/memory/rules_loader.py` | Rules 目录加载器，支持条件加载 |
| `src/memory/memory_index.py` | 记忆索引管理，支持全局+项目合并 |
| `src/memory/memory_promotion.py` | 记忆提权协议，分类判断与提权 |
| `src/memory/memory_writer.py` | extractMemories 后台代理，记忆写入 |
| `src/memory/memory_reader.py` | findRelevantMemories，小模型选择器 |
| `src/memory/memory_validator.py` | 记忆格式校验、老化判断、主动验证 |
| `src/tools/memory/topic_tools.py` | 主题文件读取工具（供模型调用） |
| `~/.my-agent/settings.json` | 全局配置模板 |
| `~/.my-agent/CLAUDE.md` | 全局指导文件模板 |
| `~/.my-agent/USER.md` | 全局用户画像模板 |
| `~/.my-agent/MEMORY.md` | 全局记忆索引模板 |
| `~/.my-agent/rules/behavior.md` | 全局行为规则模板 |
| `.my-agent/settings.json` | 项目配置模板 |
| `.my-agent/CLAUDE.md` | 项目指导文件模板 |
| `.my-agent/USER.md` | 项目用户画像模板 |
| `.my-agent/MEMORY.md` | 项目记忆索引模板 |
| `.my-agent/rules/project-behavior.md` | 项目行为规则模板 |

### 9.2 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `src/infra/config.py` | 新增多层级配置合并逻辑 |
| `src/memory/context_files.py` | 修改为支持六层 CLAUDE.md 加载 + @include 解析 |
| `src/tools/memory/tools.py` | 更新支持多层级记忆读写 |

---

## 十、实施计划

### Phase 1：基础架构（1-2天）
- 实现路径管理扩展（`src/infra/paths.py`）
- 实现配置分层合并逻辑（`src/infra/config.py`）
- 创建 Rules 目录结构和加载器（`src/memory/rules_loader.py`）

### Phase 2：静态层完善（1-2天）
- 实现六层 CLAUDE.md 加载逻辑
- 实现 @include 指令解析（含循环引用检测）
- 实现 Rules 条件加载（paths 匹配）

### Phase 3：动态层核心（2-3天）
- 实现记忆索引管理（`src/memory/memory_index.py`）
- 实现 extractMemories 后台代理（`src/memory/memory_writer.py`）
- 实现 findRelevantMemories 小模型选择器（`src/memory/memory_reader.py`）
- 实现记忆老化 + 主动验证机制（`src/memory/memory_validator.py`）

### Phase 4：记忆提权协议（1-2天）
- 实现分类判断逻辑（`src/memory/memory_promotion.py`）
- 集成到 extractMemories 流程
- 实现行为规则自动写入 Rules 目录

### Phase 5：测试与优化（1天）
- 编写单元测试
- 验证上下文占用优化效果
- 测试记忆提权流程
- 测试老化警告和主动验证机制

---

## 十一、预期效果

| 指标 | 当前状态 | 优化后 |
|------|---------|--------|
| MEMORY 上下文占用 | ~4500 字符（全量） | ~2500 字符（仅索引） |
| 行为规则约束力 | 弱（参考式 framing） | 强（命令式 framing） |
| 记忆检索效率 | 线性搜索 | 小模型选择 + 过滤机制 |
| 配置灵活性 | 单一文件 | 六层叠加，团队共享 |
| 记忆新鲜度 | 无老化机制 | 2天警告 + 主动验证 |
| 写入成本 | 主模型分心写入 | 后台代理，复用 prompt cache |

---

## 十二、关键接口定义

### 12.1 extractMemories（记忆写入代理）

**触发时机**：每轮对话完整结束后（`stopHook` 钩子）

**输入参数**：
```python
class ExtractMemoriesInput:
    conversation_id: str           # 当前会话ID
    messages: List[Message]        # 本轮对话消息列表
    has_memory_writes_since: float # 上次写入时间戳（用于去重）
    current_work_dir: str          # 当前工作目录
```

**输出参数**：
```python
class ExtractMemoriesOutput:
    memories_written: List[MemoryWriteResult]  # 写入的记忆列表
    index_updated: bool                        # 是否更新了索引

class MemoryWriteResult:
    file_name: str        # 生成的文件名（如 feedback-no-mock.md）
    memory_type: str      # user/feedback/project/reference
    name: str             # 记忆名称
    description: str      # 记忆描述
```

**fork 对话实现方式**：
- 使用 `runForkedAgent` 模式，完美复刻主对话
- 复用主对话的 prompt cache（已计算的 system prompt）
- 仅传入对话历史，不重新加载完整 context

### 12.2 findRelevantMemories（记忆检索选择器）

**触发时机**：每轮用户提问时，在构建 system prompt 之前

**输入参数**：
```python
class FindRelevantMemoriesInput:
    query: str                           # 用户当前问题
    memory_files: List[MemoryMetadata]   # 所有记忆文件的元数据（只读frontmatter）
    already_surfaced: List[str]          # 上一轮已露脸的记忆文件名列表
    recent_tools: List[str]              # 最近使用的工具名称列表
    max_results: int = 5                 # 返回最大数量
```

**输出参数（JSON schema）**：
```json
{
  "type": "object",
  "properties": {
    "memories": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "file_name": { "type": "string" },
          "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
          "reason": { "type": "string" }
        },
        "required": ["file_name", "confidence"]
      }
    }
  },
  "required": ["memories"]
}
```

**检索提示词模板**：
```
Query: {query}

Available memories:
{memory_list}

Return top-{max_results} memories that you are CERTAIN will be helpful.
Only include memories that directly relate to the query.
Be selective and discerning.
If uncertain, do not include.

Format: JSON object with "memories" array containing file_name, confidence (0-1), and reason.
```

### 12.3 alreadySurfaced 传递机制

**传递方式**：在对话状态中维护一个「已露脸记忆」集合

```python
class ConversationState:
    already_surfaced_memories: Set[str]  # 本轮已注入的记忆文件名
    
    def add_surfaced(self, file_names: List[str]):
        self.already_surfaced_memories.update(file_names)
    
    def clear(self):
        self.already_surfaced_memories.clear()
```

**清理时机**：每轮对话开始时清空，确保每轮独立选择

---

## 十三、迁移方案（v1 → v2）

### 13.1 旧格式（v1）

```markdown
# Agent 记忆索引

## 主题列表
- **user-preferences**（用户偏好）：用户是 AI 工程师，偏好架构约束
- **feedback-rules**（反馈规则）：用户要求不要在测试中 mock 数据库

## 主题文件（聚合式）
# feedback-rules.md
## 2026-07-05
- 不要在测试中 mock 数据库，使用真实数据库连接
## 2026-07-03
- API 响应时间超过 3s 需要优化
```

### 13.2 新格式（v2）

一记忆一文件 + frontmatter：

```markdown
# feedback-no-mock.md
---
name: 不要用 mock 数据库
description: 集成测试必须连真实数据库
type: feedback
created: 2026-07-05
updated: 2026-07-05
tags: [testing, database]
---
集成测试必须连真实数据库，不要用 mock。
**Why:** 用户反馈 mock 测试骗过了 CI
**How to apply:** 所有集成测试 case
```

### 13.3 转换逻辑

**自动迁移脚本**（`scripts/migrate_memory_v1_to_v2.py`）：

```python
def migrate_v1_to_v2(old_memory_path: str, new_memory_dir: str):
    # 1. 读取旧 MEMORY.md 索引
    index_content = read_file(old_memory_path)
    
    # 2. 解析主题列表，提取每个主题的描述
    topics = parse_topics(index_content)
    
    # 3. 读取每个主题文件，拆分为独立记忆
    for topic in topics:
        topic_content = read_file(f"{old_memory_path}/../memory/{topic.name}.md")
        memories = split_topic_to_memories(topic_content, topic.type)
        
        # 4. 写入新格式文件
        for memory in memories:
            write_new_memory_file(new_memory_dir, memory)
    
    # 5. 生成新 MEMORY.md 索引
    generate_new_index(new_memory_dir)
```

**拆分规则**：
- feedback 类型：每条带日期的记录拆分为独立记忆文件
- project 类型：每条项目动态拆分为独立记忆文件
- user 类型：合并为一个完整的用户画像文件
- reference 类型：每条外部指针拆分为独立记忆文件

### 13.4 向后兼容

- 首次启动时检测旧格式文件，自动执行迁移
- 迁移完成后重命名旧目录为 `data/workspace/MEMORY.md.bak`
- 保留旧格式读取能力（只读），写入仅使用新格式

---

## 十四、风险与注意事项

1. **向后兼容性**：现有 `data/workspace/MEMORY.md` 需要平滑迁移到 `.my-agent/MEMORY.md`
2. **Context 压缩**：确保 Rules 在压缩后能正确重新注入
3. **分类准确性**：LLM 分类判断可能出错，需要人工复核机制
4. **存储大小**：记忆文件可能无限增长，需要定期清理策略
5. **性能**：多层级加载可能增加启动时间，需要缓存机制
6. **老化误报**：2天警告可能过于激进，需要根据项目节奏可配置
7. **选择器成本**：Sonnet 选择器每次调用有成本，需要控制调用频率
8. **循环引用**：@include 指令需要完善的循环检测机制

---

## 十五、参考资料

- Claude Code 系列05：记忆全景——从 Session 到 Memory 的六层持久化体系
- [项目现有记忆模块](src/memory/)
- [项目现有配置模块](src/infra/config.py)
- [项目现有路径模块](src/infra/paths.py)