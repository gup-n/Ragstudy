# RAG 文档处理管线

基于 **LangChain** 构建的检索增强生成（RAG）文档处理管线，支持完整的**加载 → 切割 → 向量化 → 检索 → LLM 问答**流程。

## 项目结构

```
.
├── main.py                    # 入口：端到端管线（load → split → store → query）
├── query_demo.py              # 查询演示脚本（单次 / 交互模式）
├── answer_demo.py             # 问答演示脚本（检索 + LLM）
├── llm_config_demo.py         # Chat LLM 配置向导（API / 本地模型）
├── rag_service.py             # 服务层：CLI / Web API 复用的管线能力
├── rag_chain.py               # RAG 问答链：上下文拼接、LLM 调用、来源引用
├── .env.example               # LLM 环境变量兜底示例（仅占位符）
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
├── llm/                       # ❹ Chat LLM 配置与工厂
│   ├── __init__.py
│   ├── config.py              #   默认 Provider 参数
│   ├── schema.py              #   Pydantic 模型 + 异常定义
│   ├── models.py              #   SQLAlchemy ORM
│   ├── crud.py                #   配置 CRUD + API Key 加解密
│   ├── env.py                 #   RAG_LLM_* 环境变量兜底
│   ├── providers.py           #   Provider 工厂注册表
│   ├── factory.py             #   创建 Chat Model 实例
│   └── manager.py             #   统一对外接口
│
├── vector_store/              # ❺ 向量存储与检索
│   ├── __init__.py
│   ├── config.py              #   ChromaDB 持久化路径
│   └── store.py               #   增量入库 / 语义检索 / 文件指纹追踪
│
├── api/                       # ❻ FastAPI 后端
│   ├── app.py                 #   API 应用与路由
│   └── schemas.py             #   请求 / 响应模型
│
├── web/                       # ❼ Streamlit 前端
│   └── streamlit_app.py       #   RAG 控制台页面
│
└── Data/                      # 数据目录
    ├── docs/                  #   文档存放目录
    ├── vector_store/          #   ChromaDB 持久化目录 (自动生成)
    ├── encryption.key         #   API Key 加密密钥 (自动生成)
    └── rag.db                 #   Embedding / LLM 配置数据库 (自动生成)
```

## 快速开始

```bash
# 安装依赖
uv sync

# 0️⃣ 首次使用需先配置 Embedding Provider
uv run python config_demo.py

# 0.5️⃣ 如需完整问答，再配置 Chat LLM（API Key 或本地 Ollama 模型）
uv run python llm_config_demo.py

# 1️⃣ 入库文档（增量模式：新增/变更的文件自动处理，未变的跳过）
uv run python main.py --store

# 2️⃣ 查询演示（会展示相关性分数）
uv run python query_demo.py "RAG 的工作原理"

# 3️⃣ 完整问答
uv run python answer_demo.py "RAG 的工作原理"

# 4️⃣ 启动 Web API
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000

# 5️⃣ 另开终端启动 Streamlit 页面
uv run streamlit run web/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

## 管线流程

```
原始文档 (PDF / TXT / MD / DOCX)
    │
    ▼ data_loader.loader
List[Document]         ← page_content + metadata(source, source_id, relative_path)
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
| PDF    | `.pdf`   | `pypdf`          | 轻量读取文本型 PDF       |
| Word   | `.docx`  | `python-docx`    | 读取段落和表格文本       |

默认递归扫描 `Data/docs/`，不支持的扩展名和空内容文件会被自动跳过并记录。旧版 Word `.doc` 当前不在支持范围内，如需入库请先转换为 `.docx`。每个文档都会写入稳定的 `source_id`（相对路径），用于增量入库、删除和引用溯源。

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

## Chat LLM Provider

完整问答链支持两类 Chat LLM 配置，配置同样存储在 `Data/rag.db`，API Key 使用 Fernet 加密：

| Provider | 说明 | API Key 加密 |
|---|---|---|
| **OpenAI-Compatible** | OpenAI / DeepSeek / 硅基流动 / OneAPI 等兼容 Chat API | Fernet 加密 |
| **Ollama** | 本地 Ollama Chat 模型 | 不涉及 |

推荐使用配置向导：

```bash
uv run python llm_config_demo.py
```

向导会让用户选择 API 模型或本地模型：

- 选择 `OpenAI-Compatible` 时填写模型名、API 地址和 API Key。
- 选择 `Ollama` 时填写本地服务地址和模型名。
- 保存后同一时间仅启用一条 LLM 配置。

`.env.example` 仍保留为部署兜底示例：当数据库中没有启用的 LLM 配置时，系统会尝试读取本机 `.env` 或环境变量中的 `RAG_LLM_*`。真实 API Key 只应写入本机配置或环境变量，不要写入文档、日志或提交记录。

## 向量存储（ChromaDB）

文档向量化后存入 ChromaDB，支持增量更新。

### 入库文档

```bash
# 增量入库（默认）：对比文件指纹，新增/变更的入库，未变的跳过
uv run python main.py --store

# 增量入库，并清理本次扫描目录中已经删除的旧文件向量
uv run python main.py --store --prune-deleted

# 全量重建：清空后重新入库所有文档
uv run python main.py --store --reindex
```

**增量入库策略：**
- 入库时在 metadata 中记录 `source_id`、`file_mtime`、`file_size`、`content_hash`
- 下次入库前对比：
  | 情况 | 处理方式 |
  |------|----------|
  | 新文件 | 直接入库 |
  | 文件已变更（内容哈希或 mtime/size 不同） | 先删旧向量 → 重新入库 |
  | 文件未变更 | 跳过 |
  | 文件已删除（使用 `--prune-deleted`） | 删除旧向量 |
- 因此重复运行 `--store` 不会产生重复数据
- 使用 `--prune-deleted` 时会启用严格加载；如果本次扫描中有文件解析失败，会停止清理，避免把临时加载失败误判为文件已删除。

### 查询演示（无需 LLM）

```bash
# 单次查询
uv run python query_demo.py "RAG 的工作原理"

# 交互模式（反复提问）
uv run python query_demo.py

# 指定返回数量
uv run python query_demo.py "向量化" --top-k 10

# 设置最低相关性分数
uv run python query_demo.py "向量化" --score-threshold 0.3
```

查询结果展示：相关性分数、文件来源、匹配内容片段，不调用 LLM，用于验证检索效果。

### RAG 问答演示（需要 Chat LLM）

问答链会先复用 `rag_service.retrieve()` 检索相关片段，再把片段拼接为带编号的上下文，最后调用 Chat LLM 生成带引用的回答。

1. 运行 `uv run python llm_config_demo.py` 配置 API Key 或本地模型。
2. 如用于部署，也可复制 `.env.example` 为 `.env` 并填写 `RAG_LLM_*` 作为兜底配置。
3. 确保已入库文档：`uv run python main.py --store`。

```bash
# 单次问答
uv run python answer_demo.py "奖学金如何申请？"

# 交互模式
uv run python answer_demo.py

# 指定检索片段数和相关性阈值
uv run python answer_demo.py "学生证如何补办？" --top-k 8 --score-threshold 0.3

# 调试时查看实际发送给 LLM 的上下文
uv run python answer_demo.py "考试违纪怎么处理？" --show-context
```

可选 LLM 环境变量：

| 变量 | 说明 |
|---|---|
| `RAG_LLM_PROVIDER` | `openai-compatible` 或 `ollama` |
| `RAG_LLM_MODEL` | Chat 模型名称 |
| `RAG_LLM_BASE_URL` | 服务地址，OpenAI-compatible 默认 `https://api.openai.com/v1`，Ollama 默认 `http://localhost:11434` |
| `RAG_LLM_API_KEY` | API Key；Ollama 本地模型通常可留空 |
| `RAG_LLM_TEMPERATURE` | 生成温度，默认 `0.2` |
| `RAG_LLM_TIMEOUT` | OpenAI-compatible 请求超时秒数，默认 `60` |

## Web API 与页面

FastAPI 后端复用 `rag_service.py` 和 `rag_chain.py`，Streamlit 页面通过 HTTP 连接后端，不重复业务逻辑。

### 启动命令

```bash
# 终端 1：启动后端
uv run uvicorn api.app:app --host 127.0.0.1 --port 8000

# 终端 2：启动前端
uv run streamlit run web/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

访问地址：

- FastAPI：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- Streamlit 控制台：`http://127.0.0.1:8501`

如果 API 地址不是默认值，可设置环境变量或在页面侧边栏修改：

```bash
RAG_API_BASE_URL=http://127.0.0.1:8000
```

### API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `GET` | `/config/status` | Embedding / LLM 配置状态，不返回密钥 |
| `GET` | `/stats` | 向量库 Chunk 数和文件列表 |
| `POST` | `/index` | 文档入库，支持增量、全量重建和清理已删除文件 |
| `POST` | `/retrieve` | 语义检索并返回片段和分数 |
| `POST` | `/answer` | RAG 问答并返回答案和引用来源 |

### 页面功能

Streamlit 控制台包含四个页面：

- 状态：查看 API、配置和向量库状态。
- 入库：触发文档入库。
- 检索：执行语义检索，查看片段和 metadata。
- 问答：调用 RAG 问答链，查看答案和引用来源。

## 操作模式一览

| 命令 | 说明 |
|------|------|
| `uv run python main.py` | 管线：加载 → 切割 → 验证 Embedding |
| `uv run python main.py --store` | 入库：加载 → 切割 → Embedding → ChromaDB（增量） |
| `uv run python main.py --store --prune-deleted` | 增量入库并清理已删除源文件 |
| `uv run python main.py --store --reindex` | 全量重建入库 |
| `uv run python main.py --query "..."` | 检索：从 ChromaDB 搜索并展示结果 |
| `uv run python main.py --query "..." --score-threshold 0.3` | 带相关性阈值检索 |
| `uv run python main.py --skip-embed` | 仅加载 + 切割，跳过 Embedding |
| `uv run python config_demo.py` | 配置 Embedding Provider |
| `uv run python llm_config_demo.py` | 配置 Chat LLM Provider |
| `uv run python query_demo.py` | 交互式查询演示 |
| `uv run python query_demo.py "..."` | 单次查询演示 |
| `uv run python answer_demo.py` | 交互式 RAG 问答 |
| `uv run python answer_demo.py "..."` | 单次 RAG 问答 |
| `uv run uvicorn api.app:app --host 127.0.0.1 --port 8000` | 启动 FastAPI 后端 |
| `uv run streamlit run web/streamlit_app.py --server.address 127.0.0.1 --server.port 8501` | 启动 Streamlit 页面 |

## 开发

```bash
# 安装开发依赖
uv sync --group dev

# 运行测试
uv run pytest tests

# 代码检查
uv run ruff check .

# 格式化
uv run ruff format .
```

## 许可证

MIT
