# 知识库 RAG

基于 FAISS 向量索引 + fastembed 本地 embedding 的个人知识库检索增强生成（RAG）。

## 源码位置

```
src/tools/rag/
└── tools.py          # search_notes 工具

src/memory/
├── rag.py            # 文档 ingest、向量检索
├── rag_worker.py     # 子进程 ingest
└── embeddings.py     # Embedding 模型封装
```

## 工具

| 工具 | 说明 |
|------|------|
| `search_notes` | 在知识库中语义检索相关文档片段 |

## 工作流程

### 文档入库（Ingest）

1. 扫描 `data/workspace/knowledge/` 目录
2. 支持格式：`.txt`、`.md`、`.pdf`、`.docx`
3. 文本分块（chunk_size=500, overlap=80）
4. 本地 embedding 向量化（BAAI/bge-small-zh-v1.5）
5. 写入 FAISS 索引（`data/vectorstore/`）

### 检索问答

1. 用户提问涉及上传文档时，Agent 优先调用 `search_notes`
2. 查询向量化 → FAISS 相似度检索 → 返回 top_k 片段
3. Agent 基于检索结果生成回答

## Embedding 模式

`config/search.yaml` 中 `rag.embedding_mode`：

| 模式 | 说明 |
|------|------|
| `local` | 本地 fastembed（推荐，无需 API Key） |
| `api` | 调用 Embedding API（text-embedding-3-small） |
| `auto` | 自动选择 |

## 配置

```yaml
rag:
  embedding_mode: local
  local_embedding_model: BAAI/bge-small-zh-v1.5
  chunk_size: 500
  chunk_overlap: 80
  top_k: 4
  supported_extensions:
    - .txt
    - .md
    - .pdf
    - .docx
```

## 数据目录

| 路径 | 用途 |
|------|------|
| `data/workspace/knowledge/` | 待索引的文档源 |
| `data/vectorstore/` | FAISS 索引文件 |
| `data/vectorstore/index_meta.json` | 索引元数据（文件 hash、更新时间） |

## Web UI 管理

Web 前端提供「知识库」模态窗口，支持：

- 查看已索引文档列表
- 上传新文档
- 触发重新索引
- 删除文档

## 使用示例

- 「我上传的产品手册里怎么配置 API？」→ Agent 调用 search_notes
- 用户上传 PDF 到知识库目录后，相关问题自动走 RAG 检索
