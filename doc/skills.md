# Skill 扩展

Skill 是可插拔的脚本扩展机制，用户可在指定目录放置 `SKILL.md` + 脚本，通过斜杠命令调用。

## 源码位置

```
src/ui/skill/
├── catalog.py    # Skill 目录扫描、斜杠命令注册
├── runner.py     # Skill 脚本执行
└── __init__.py

src/ui/skill_catalog.py   # 遗留入口
src/ui/skill_runner.py    # 遗留入口
```

## Skill 目录结构

```
my-skill/
├── SKILL.md          # 必需：Skill 描述文件
├── run.py            # 可选：执行脚本
└── ...               # 其他依赖文件
```

### SKILL.md 格式

```markdown
# Skill 名称

简短描述（第一行非标题文本会被用作菜单描述）

## 用法

说明如何使用此 Skill...
```

## 目录配置

在 `data/user_settings.yaml` 中配置 Skill 扫描目录：

```yaml
ui:
  skill_dirs:
    - "D:/my-skills"
    - "~/.cursor/skills"
```

## 斜杠命令注册

`catalog.py` 扫描流程：

1. 遍历 `skill_dirs` 中所有子目录
2. 查找 `SKILL.md` 文件
3. 以目录名作为 Skill 名称（如 `my-skill` → `/my-skill`）
4. 合并系统内置命令，生成完整斜杠目录

### 系统内置命令

| 命令 | 说明 |
|------|------|
| `/note` | 笔记管理 |
| `/tsk` | 任务管理 |
| `/cache` | 搜索缓存 |
| `/search` | 网络搜索 |
| `/weather` | 天气预报 |
| `/ocr` | 图片 OCR |

## 执行流程

1. 用户输入 `/my-skill arg1 arg2`
2. 意图识别为 `INTENT_SLASH_SKILL`
3. `skill/runner.py` 定位 Skill 目录
4. 执行 `run.py`（或其他入口脚本），传入参数
5. 捕获 stdout/stderr，以助手消息展示结果

## 与 Cursor Skill 的关系

项目支持扫描 Cursor 的 Skill 目录（如 `~/.cursor/skills`），但执行方式独立：

- Cursor Skill 是为 Cursor IDE Agent 设计的指令文件
- my-agent Skill 是可执行脚本的封装
- 两者目录格式兼容（都有 SKILL.md），但运行时行为不同

## 使用示例

```
/my-skill hello world
```

Composer 输入 `/` 时会显示所有已注册的 Skill 供选择。
