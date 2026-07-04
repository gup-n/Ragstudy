# RAG 文档处理管线

基于 **LangChain** 构建的检索增强生成（RAG）文档处理管线，支持完整的**加载 → 切割 → 向量化**流程。

## 项目结构

```
.
├── main.py                    # 入口：端到端管线（load → split → store → query）
├── query_demo.py              # 查询演示脚本（单次 / 交互模式）
├── pyproject.toml             # 项目元数据与依赖
├── README.md
│
├── data_loader/               # ❶ 文档加载
│   ├── __init__.py
│   ├── config.py              #   格式 → Loader 映射表
│   └── loader.py              #   目录扫描 + 多格式解析
│
├── data_splitter/             # ❷ 文本切割
│   ├── __init__.py
│   ├── config.py              #   切割策略注册表
│   └── splitter.py            #   Document → Chunks
│
├── embedding/                 # ❸ 向量化引擎
│   ├── __init__.py
│   ├── config.py              #   路径、密钥、缓存配置
│   ├── schema.py              #   Pydantic 模型 + 异常定义
│   ├── models.py              #   SQLAlchemy ORM
│   ├── database.py            #   SQLite 引擎 + Session
│   ├── crud.py                #   配置 CRUD + API Key 加解密
│   ├── providers.py           #   Provider 工厂注册表
│   ├── factory.py             #   创建 Embeddings 实例
│   ├── manager.py             #   统一对外接口
│   └── downloader.py          #   HF 模型下载
│
├── vector_store/              # ❹ 向量存储与检索
│   ├── __init__.py
│   ├── config.py              #   ChromaDB 持久化路径
│   └── store.py               #   增量入库 / 语义检索 / 文件指纹追踪
│
└── Data/                      # 数据目录
    ├── docs/                  #   文档存放目录
    ├── vector_store/          #   ChromaDB 持久化目录 (自动生成)
    ├── encryption.key         #   API Key 加密密钥 (自动生成)
    └── rag.db                 #   配置数据库 (自动生成)
```

## 快速开始

```bash
# 安装依赖
uv sync

# 0️⃣ 首次使用需先配置 Embedding Provider
uv run python -c "
from embedding import init_db, save_config
from embedding.schema import EmbeddingConfigCreate

init_db()
cfg = EmbeddingConfigCreate(
    provider='openai-compatible',
    model='text-embedding-3-small',
    base_url='https://api.openai.com/v1',
    api_key='sk-...',
)
save_config(cfg)
print('✅ 配置已保存')
"

# 1️⃣ 入库文档（增量模式：新增/变更的文件自动处理，未变的跳过）
uv run python main.py --store

# 2️⃣ 查询演示
uv run python query_demo.py "RAG 的工作原理"
```

## 管线流程

```
原始文档 (PDF / TXT / MD / DOCX)
    │
    ▼ data_loader.loader
List[Document]         ← page_content + metadata(source, filename)
    │
    ▼ data_splitter.splitter
List[Document]         ← chunk_size=800, overlap=150
    │
    ▼ embedding.manager.get_embedding()
向量                    ← HuggingFace / Ollama / OpenAI-Compatible
```

## 文档加载

| 格式   | 扩展名   | 底层库           | 说明                     |
| ------ | -------- | ---------------- | ------------------------ |
| 纯文本 | `.txt`   | 内置 `open()`    | 需 UTF-8 编码            |
| Markdown | `.md`   | 轻量读取         | 以纯文本读取，无额外依赖 |
| PDF    | `.pdf`   | `pypdf`          | 仅限文本型 PDF           |
| Word   | `.docx`  | `python-docx`    | 支持 .docx 格式          |

不支持的扩展名会被自动跳过并记录。

## 文本切割

内置两种切割策略：

| 策略        | 说明                 | 默认分隔符                                    |
| ----------- | -------------------- | --------------------------------------------- |
| `recursive` | 递归智能切割（默认） | `\n\n` → `\n` → `。` → `！` → `？` → `，` → ` ` |
| `character` | 按字符数固定切割     | `\n`                                          |

参数：`chunk_size=800`，`chunk_overlap=150`

## Embedding Provider

支持三种向量化引擎，配置存储在 `Data/rag.db`：

| Provider            | 说明                                   | API Key 加密 |
| ------------------- | -------------------------------------- | ------------ |
| **HuggingFace**     | 本地模型，通过 `HuggingFaceEmbeddings` | 不涉及       |
| **Ollama**          | 本地 Ollama 服务的 Embedding 端点      | 不涉及       |
| **OpenAI-Compatible** | OpenAI / DeepSeek / 硅基流动 等 API  | Fernet 加密  |

### 首次配置 Embedding

```python
from embedding import init_db, save_config
from embedding.schema import EmbeddingConfigCreate

init_db()

# OpenAI
cfg = EmbeddingConfigCreate(
    provider='openai-compatible',
    model='text-embedding-3-small',
    base_url='https://api.openai.com/v1',
    api_key='sk-...',
)

# 或 Ollama
cfg = EmbeddingConfigCreate(
    provider='ollama',
    model='nomic-embed-text',
    base_url='http://localhost:11434',
)

# 或 HuggingFace 本地模型
cfg = EmbeddingConfigCreate(
    provider='huggingface',
    model='BAAI/bge-small-zh-v1.5',
)

save_config(cfg)
print('配置已保存')
```

## 向量存储（ChromaDB）

文档向量化后存入 ChromaDB，支持增量更新。

### 入库文档

```bash
# 增量入库（默认）：对比文件指纹，新增/变更的入库，未变的跳过
uv run python main.py --store

# 全量重建：清空后重新入库所有文档
uv run python main.py --store --reindex
```

**增量入库策略：**
- 入库时在 metadata 中记录 `file_mtime` + `file_size`
- 下次入库前对比：
  | 情况 | 处理方式 |
  |------|----------|
  | 新文件 | 直接入库 |
  | 文件已变更（mtime/size 不同） | 先删旧向量 → 重新入库 |
  | 文件未变更 | 跳过 |
- 因此重复运行 `--store` 不会产生重复数据

### 查询演示（无需 LLM）

```bash
# 单次查询
uv run python query_demo.py "RAG 的工作原理"

# 交互模式（反复提问）
uv run python query_demo.py

# 指定返回数量
uv run python query_demo.py "向量化" --top-k 10
```

查询结果展示：文件来源、匹配内容片段，不调用 LLM，用于验证检索效果。

## 操作模式一览

| 命令 | 说明 |
|------|------|
| `uv run python main.py` | 管线：加载 → 切割 → 验证 Embedding |
| `uv run python main.py --store` | 入库：加载 → 切割 → Embedding → ChromaDB（增量） |
| `uv run python main.py --store --reindex` | 全量重建入库 |
| `uv run python main.py --query "..."` | 检索：从 ChromaDB 搜索并展示结果 |
| `uv run python main.py --skip-embed` | 仅加载 + 切割，跳过 Embedding |
| `uv run python query_demo.py` | 交互式查询演示 |
| `uv run python query_demo.py "..."` | 单次查询演示 |

## 开发

```bash
# 安装开发依赖
uv sync --group dev

# 代码检查
uv run ruff check .

# 格式化
uv run ruff format .
```

## 许可证

MIT
