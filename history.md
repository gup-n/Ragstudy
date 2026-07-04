# RAG 项目 — 开发日志

> 记录时间：首次完整搭建日
> 仓库：https://github.com/gup-n/Ragstudy.git

---

## 项目概要

基于 LangChain 的 RAG 文档处理管线，支持 **加载 → 切割 → 向量化入库 → 语义检索** 完整流程，无需 LLM 也可独立检索。

---

## 代码结构

```
rag/
├── main.py                       # 端到端入口（默认管线 / --store 入库 / --query 检索）
├── query_demo.py                 # 语义检索演示（交互模式 + 单次查询，无需 LLM）
├── config_demo.py                # Embedding 配置向导（交互式选 Provider 填参数）
├── data_loader/                  # 文档加载（TXT/MD/PDF/DOCX）
├── data_splitter/                # 文本切割（recursive / character）
├── embedding/                    # 向量化引擎（HuggingFace / Ollama / OpenAI-Compatible）
├── vector_store/                 # ChromaDB 向量存储（增量入库 / 语义检索）
└── Data/                         # 数据目录（docs/ / vector_store/ / rag.db / encryption.key）
```

---

## 关键决策记录

### 1. 文档加载器选择
- **决策**：用轻量 `SimpleMarkdownLoader` 替代 `UnstructuredMarkdownLoader`
- **理由**：`UnstructuredMarkdownLoader` 依赖 spaCy 模型（首次运行下载 ~500MB），对于纯文本 Markdown 场景过重
- **实现**：继承 `TextLoader`，编码由 `LOADER_ARGS[".md"]` 控制

### 2. 编码策略
- **决策**：所有文本 Loader 显式指定 `encoding="utf-8"`
- **理由**：Windows 默认编码非 UTF-8（cp936/GBK），不指定则含中文 UTF-8 文件解码失败
- **配置位置**：`data_loader/config.py` → `LOADER_ARGS`

### 3. Embedding 配置存储
- **决策**：SQLite + Fernet 加密 API Key
- **理由**：轻量无外部依赖，多条配置仅一条 `enabled=True`（数据库部分唯一索引保障）
- **文件**：`embedding/crud.py`（加解密）、`embedding/models.py`（ORM）

### 4. 向量库选择
- **决策**：ChromaDB（`langchain-chroma`）
- **理由**：与 LangChain 集成最佳、自动持久化、轻量无服务器
- **版本**：chromadb==1.5.9, langchain-chroma==1.1.0

### 5. 增量入库策略
- **决策**：文件指纹对比（`file_mtime` + `file_size`）
- **流程**：入库时在 ChromaDB metadata 中记录指纹 → 下次入库前对比 → 新文件入库 / 变更文件先删旧再入库 / 未变跳过
- **实现**：`vector_store/store.py` → `add_to_store()` / `get_stored_file_index()` / `delete_by_filenames()`

### 6. 配置常量 vs 数据库 Session 分离
- **问题**：`embedding/config.py` 和 `embedding/database.py` 内容完全重复，配置常量丢失
- **修复**：`config.py` 只放常量（路径/密钥/缓存），`database.py` 只放 Session 管理
- **导出模式**：`crud.py` 提供两套 API——底层 `f(session, ...)` 供内部组合，上层 `f(...)` 自动管理 Session 供外部调用

---

## 当前状态

| 模块 | 完成度 | 说明 |
|---|---|---|
| `data_loader` | ✅ 完成 | TXT/MD/PDF/DOCX，UTF-8 编码，不支持的格式自动跳过 |
| `data_splitter` | ✅ 完成 | recursive（默认）/character 两种策略 |
| `embedding/` | ✅ 完成 | 三种 Provider 配置/加解密/CRUD/验证 |
| `vector_store` | ✅ 完成 | 增量入库/全量重建/语义搜索/文件管理 |
| `query_demo` | ✅ 完成 | 交互模式 + 单次查询，不调 LLM |
| `config_demo` | ✅ 完成 | 交互式向导配置 Embedding |
| RAG 问答链 | ❌ 未开始 | 检索结果 + LLM 生成回答 |
| Web API | ❌ 未开始 | FastAPI 接口 |

---

## 常用命令速查

```bash
# 配置 Embedding
uv run python config_demo.py

# 入库文档（增量）
uv run python main.py --store

# 全量重建
uv run python main.py --store --reindex

# 查询演示
uv run python query_demo.py "你的问题"

# 交互式查询
uv run python query_demo.py

# 仅测试管线（加载+切割）
uv run python main.py --skip-embed

# 代码检查
uv run ruff check .

# 运行
uv run python main.py
```

---

## 下次继续的起点 Prompt

> 这是一个 RAG 文档处理管线项目，仓库在 https://github.com/gup-n/Ragstudy.git。
>
> 当前已完成：文档加载（TXT/MD/PDF/DOCX）、文本切割（recursive/character）、三种 Embedding Provider 配置管理（HuggingFace/Ollama/OpenAI-Compatible）、ChromaDB 向量存储（增量入库 + 语义检索）、三个入口脚本（main.py / query_demo.py / config_demo.py）。
>
> 还未做的：RAG 问答链（检索 + LLM 生成回答）、Web API（FastAPI）、增量更新优化。
>
> 关键记忆点：
> - 文本 Loader 需显式指定 `encoding="utf-8"`（Windows 兼容）
> - `vector_store/store.py` 有增量入库逻辑，入库时记录 `file_mtime` + `file_size` 指纹
> - `embedding/crud.py` 分两层 API：`f(session, ...)` 底层的和 `f(...)` 自动管理 Session 的
> - API Key 用 Fernet 加密存储在 SQLite 中
> - 所有配置常量集中在 `embedding/config.py`
