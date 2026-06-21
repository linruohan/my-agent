# 本地文件工具

提供 20 个本地文件系统操作工具，Agent 可通过自然语言搜索、读取、写入和管理本地文件。

## 源码位置

```
src/tools/file/
├── tools.py      # 工具注册与 search_tools_status
├── search.py     # find_files, grep_files, list_directory, read_local_file
├── ops.py        # 复制/移动/删除/重命名/目录操作
├── meta.py       # 路径信息、属性、磁盘用量
└── advanced.py   # 二进制读取、分块读取、符号链接
```

## 工具列表

### 搜索与浏览

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `search_tools_status` | 检查 fd/rg CLI 是否可用 | 否 |
| `find_files` | 按文件名模式搜索（优先 fd，回退 os.walk） | 否 |
| `grep_files` | 按内容搜索（优先 ripgrep，回退 Python） | 否 |
| `list_directory` | 列出目录内容 | 否 |
| `read_local_file` | 读取文本文件 | 否 |

### 写入与创建

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `create_file` | 创建新文件 | 是 |
| `write_local_file` | 写入/覆盖文件 | 是 |
| `write_local_file_locked` | 带文件锁的写入 | 是 |
| `create_directory` | 创建目录 | 否 |

### 删除与移动

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `delete_path` | 删除文件或目录 | 是 |
| `remove_directory` | 删除目录 | 是 |
| `copy_path` | 复制文件/目录 | 是 |
| `move_path` | 移动文件/目录 | 是 |
| `rename_path` | 重命名 | 是 |

### 元数据与进阶

| 工具 | 说明 | 需确认 |
|------|------|--------|
| `get_path_info` | 文件/目录元信息 | 否 |
| `set_file_attributes` | 设置文件属性 | 是 |
| `get_disk_usage` | 磁盘空间用量 | 否 |
| `read_file_bytes` | 读取二进制内容 | 否 |
| `stream_read_file` | 分块读取大文件 | 否 |
| `create_symlink` | 创建符号链接 | 是 |

## 搜索根目录限制

文件操作范围受 `config/files.yaml` 中 `search_roots` 约束，默认包括：

- 用户主目录 `~`
- 项目代码目录
- `data/workspace`

Agent 无法访问 search_roots 之外的文件，防止误操作。

## CLI 工具依赖

| CLI | 用途 | 回退方案 |
|-----|------|----------|
| `fd` | 文件名搜索 | Python os.walk |
| `rg` (ripgrep) | 内容搜索 | Python 逐行扫描 |

可通过 `search_tools_status` 工具检查安装状态。建议安装 fd 和 rg 以获得最佳性能。

## 配置

`config/files.yaml`：

```yaml
search_roots:
  - "~"
  - "D:/codehub"
  - "data/workspace"
prefer_fd: true
prefer_rg: true
max_results: 50
max_read_bytes: 1048576  # 1MB
```

## 使用示例

用户可以通过自然语言触发：

- 「在 D 盘 codehub 下找所有 Python 文件」→ `find_files`
- 「搜索包含 TODO 的代码」→ `grep_files`
- 「读取 config/app.yaml 的内容」→ `read_local_file`
- 「把 notes.txt 复制到 backup 目录」→ `copy_path`（需确认）
