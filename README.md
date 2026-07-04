# RAG 文档处理管线

基于 **LangChain** 构建的检索增强生成（RAG）文档处理管线，支持完整的**加载 → 切割 → 向量化**流程。

## 项目结构

```
.
├── main.py                    # 入口：端到端管线（支持命令行参数）
├── pyproject.toml             # 项目元数据与依赖
├── README.md
│
├── data_loader/               # ❶ 文档加载
│   ├── __init__.py            #   公开 API
│   ├── config.py              #   格式 → Loader 映射表
│   └── loader.py              #   核心：目录扫描 + 多格式解析
│
├── data_splitter/             # ❷ 文本切割
│   ├── __init__.py            #   公开 API
│   ├── config.py              #   切割策略注册表
│   └── splitter.py            #   核心：Document → Chunks
│
├── embedding/                 # ❸ 向量化引擎
│   ├── __init__.py            #   公开 API
│   ├── config.py              #   路径、密钥、缓存等配置
│   ├── schema.py              #   Pydantic 数据模型 + 异常定义
│   ├── models.py              #   SQLAlchemy ORM 模型
│   ├── database.py            #   SQLite 引擎 + Session 管理
│   ├── crud.py                #   配置的增删改查 + API Key 加解密
│   ├── providers.py           #   Provider 工厂注册表
│   ├── factory.py             #   根据配置创建 Embeddings 实例
│   ├── manager.py             #   统一对外接口
│   └── downloader.py          #   HuggingFace 模型下载
│
└── Data/                      # 数据目录（自动生成）
    ├── docs/                  #   文档存放目录
    ├── encryption.key         #   API Key 加密密钥
    └── rag.db                 #   SQLite 配置文件数据库
```

## 快速开始

```bash
# 安装依赖
uv sync

# 运行完整管线（加载 → 切割 → 向量化）
uv run python main.py

# 仅执行加载和切割（跳过向量化）
uv run python main.py --skip-embed

# 指定文档目录和切割策略
uv run python main.py --dir path/to/docs --splitter character
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
