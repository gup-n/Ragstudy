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
- **实现**：`vector_store/store.py` → `add_to_store()` / `get_stored_file_index()` / `delete_by_source_ids()`

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

## 后续优化记录

### 2026-07-05
- 新增 `rag_service.py` 服务层，CLI、查询演示和后续 Web API 可复用同一套加载、切割、入库、检索逻辑
- 文档目录统一为 `Data/docs`，默认递归扫描，并写入 `doc_root`、`relative_path`、`source_id`、`file_ext` 等 metadata
- PDF 加载改为轻量 `PyPDFLoader`，DOCX 加载改为基于项目已声明的 `python-docx`
- 文本切割后为每个 Chunk 写入稳定 `chunk_index` 和 `chunk_id`
- 向量库增量判断从 `filename + mtime/size` 升级为 `source_id + content_hash + mtime/size`
- 新增 `delete_by_source_ids()`、`search_with_scores()`，查询演示和主入口支持展示相关性分数
- `main.py --store --prune-deleted` 可清理本次扫描目录中已删除源文件的旧向量
- Embedding 配置增加 Provider/模型校验，配置更新支持清空可选字段
- 新增轻量单元测试覆盖加载、切割、向量 metadata 和 Embedding 配置校验

### 2026-07-05 交付整理记录
- 新增 `PROJECT_REPORT.md`，记录本次操作、当前功能、未完成部分、依赖安装方式和新会话 Prompt
- 新增 `CODE_NOTES.md`，为每份代码整理整体功能、方法功能和关键变量
- 依赖声明补齐：`huggingface-hub` 加入基础依赖，`pytest` 加入开发依赖组
- 代码补充少量解释性注释，重点说明 `source_id`、空库短路、历史索引兼容和已删除文件清理边界

#### 当前代码状态
- 主业务入口已收敛到 `rag_service.py`
- `main.py` 负责命令行参数和输出
- `query_demo.py` 负责无 LLM 检索演示
- `config_demo.py` 负责交互式 Embedding 配置
- 文档加载默认递归，并以相对路径作为 `source_id`
- 向量库存储以 `source_id` 为文件身份，以 `chunk_id` 为片段身份
- 增量判断优先使用 `content_hash`，旧数据兼容 `mtime + size`
- 敏感运行数据仍由 `.gitignore` 排除，包括 `Data/encryption.key`、`Data/rag.db`、`Data/vector_store/`、`Data/hf_cache/`

#### 新会话 Prompt

> 继续维护 `F:\coding\python\project\RAG` 这个 RAG 项目，仓库为 `https://github.com/gup-n/Ragstudy.git`。
>
> 当前项目已经完成：文档加载 TXT/MD/PDF/DOCX、递归扫描、文本切割、Embedding 配置管理、ChromaDB 向量存储、增量入库、已删除文件清理、带分数语义检索、服务层 `rag_service.py`、入口脚本 `main.py`、`query_demo.py`、`config_demo.py`。
>
> 关键决策：文档目录是 `Data/docs`；文件身份是 `source_id`，来自相对路径；Chunk 身份是 `chunk_id`；增量入库使用 `content_hash + mtime + size`；查询分数由 `search_with_scores()` 返回；API Key 用 Fernet 加密存储在 SQLite。
>
> 已新增文档：`PROJECT_REPORT.md` 和 `CODE_NOTES.md`。已新增测试目录 `tests/`。
>
> 下一步优先事项：先运行 `uv lock`、`uv sync --group dev`、`uv run pytest tests`、`uv run ruff check .`，然后实现完整 RAG 问答链或 FastAPI Web API。继续开发时优先复用 `rag_service.py`。

### 2026-07-05 测试后状态记录
- Python 语法编译通过
- Ruff 静态检查通过
- Git 空白检查通过
- 手动逻辑检查通过，检查脚本为 `tests/manual_logic_check.py`
- `pytest tests` 未执行，原因是当前虚拟环境没有 `pytest` 命令，当前终端找不到 `uv`
- 已将 `pytest` 写入开发依赖组，后续在具备 `uv` 的环境中执行 `uv sync --group dev`

#### 测试后确认功能
- 支持 TXT、MD、PDF、DOCX 加载
- 支持递归扫描和一级扫描
- 支持稳定 `source_id` 和 `chunk_id`
- 支持 Embedding 配置、加密存储和校验
- 支持 ChromaDB 增量入库、全量重建和已删除文件清理
- 支持带分数语义检索
- 支持服务层复用

#### 测试后未完成事项
- 更新 `uv.lock`
- 安装开发依赖并运行 `pytest tests`
- 实现 RAG 问答链
- 实现 FastAPI Web API
- 增强检索质量，如 MMR、过滤、重排序

#### 测试后新会话 Prompt

> 继续维护 `F:\coding\python\project\RAG`。本轮已完成服务层抽象、递归加载、稳定文件身份、稳定 Chunk 身份、内容哈希增量入库、已删除文件清理、带分数检索、文档整理和轻量测试。
>
> 关键文件：`rag_service.py`、`main.py`、`query_demo.py`、`config_demo.py`、`vector_store/store.py`、`data_loader/loader.py`、`PROJECT_REPORT.md`、`CODE_NOTES.md`、`history.md`。
>
> 已通过：语法编译、ruff、git 空白检查、`tests/manual_logic_check.py`。尚未通过 pytest，因为当前环境缺少 pytest 命令。
>
> 下一步先运行 `uv lock`、`uv sync --group dev`、`uv run pytest tests`、`uv run ruff check .`。之后优先实现 RAG 问答链或 FastAPI，继续复用 `rag_service.py`。

---

## 常用命令速查

```bash
# 配置 Embedding
uv run python config_demo.py

# 入库文档（增量）
uv run python main.py --store

# 入库文档并清理已删除源文件
uv run python main.py --store --prune-deleted

# 全量重建
uv run python main.py --store --reindex

# 查询演示
uv run python query_demo.py "你的问题"

# 带相关性阈值查询
uv run python query_demo.py "你的问题" --score-threshold 0.3

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
> 当前已完成：文档加载（TXT/MD/PDF/DOCX）、文本切割（recursive/character）、
> 三种 Embedding Provider 配置管理（HuggingFace/Ollama/OpenAI-Compatible）、
> ChromaDB 向量存储（增量入库 + 语义检索）、
> 服务层 `rag_service.py` 与三个入口脚本（main.py / query_demo.py / config_demo.py）。
>
> 还未做的：RAG 问答链（检索 + LLM 生成回答）、Web API（FastAPI）、增量更新优化。
>
> 关键记忆点：
> - 文本 Loader 需显式指定 `encoding="utf-8"`（Windows 兼容）
> - `vector_store/store.py` 有增量入库逻辑，入库时记录 `file_mtime` + `file_size` 指纹
> - `embedding/crud.py` 分两层 API：`f(session, ...)` 底层的和 `f(...)` 自动管理 Session 的
> - API Key 用 Fernet 加密存储在 SQLite 中
> - 所有配置常量集中在 `embedding/config.py`
