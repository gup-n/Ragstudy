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
├── answer_demo.py                # RAG 问答演示（检索 + LLM）
├── llm_config_demo.py            # Chat LLM 配置向导（API / 本地模型）
├── rag_chain.py                  # RAG 问答链（上下文拼接 / LLM 调用 / 来源引用）
├── config_demo.py                # Embedding 配置向导（交互式选 Provider 填参数）
├── data_loader/                  # 文档加载（TXT/MD/PDF/DOCX）
├── data_splitter/                # 文本切割（recursive / character）
├── embedding/                    # 向量化引擎（HuggingFace / Ollama / OpenAI-Compatible）
├── llm/                          # Chat LLM 配置与工厂（OpenAI-Compatible / Ollama）
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
| `llm/` | ✅ 基础版完成 | LLM 配置存储/加解密/Provider 工厂/环境变量兜底 |
| RAG 问答链 | ✅ 基础版完成 | 检索结果 + LLM 生成带引用回答 |
| Web API | ✅ 基础版完成 | FastAPI 状态/入库/检索/问答接口 |
| Web 页面 | ✅ 基础版完成 | Streamlit 控制台连接 FastAPI |

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
> 下一步优先事项：先运行 `uv lock`、`uv sync --group dev`、`uv run pytest tests`、`uv run ruff check .`，然后实现 FastAPI Web API 或继续增强基础版 RAG 问答链。继续开发时优先复用 `rag_service.py`。

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
- 增强 RAG 问答链（多轮对话、引用去重、上下文压缩）
- 实现 FastAPI Web API
- 增强检索质量，如 MMR、过滤、重排序

#### 测试后新会话 Prompt

> 继续维护 `F:\coding\python\project\RAG`。本轮已完成服务层抽象、递归加载、稳定文件身份、稳定 Chunk 身份、内容哈希增量入库、已删除文件清理、带分数检索、文档整理和轻量测试。
>
> 关键文件：`rag_service.py`、`main.py`、`query_demo.py`、`config_demo.py`、`vector_store/store.py`、`data_loader/loader.py`、`PROJECT_REPORT.md`、`CODE_NOTES.md`、`history.md`。
>
> 已通过：语法编译、ruff、git 空白检查、`tests/manual_logic_check.py`。尚未通过 pytest，因为当前环境缺少 pytest 命令。
>
> 下一步先运行 `uv lock`、`uv sync --group dev`、`uv run pytest tests`、`uv run ruff check .`。之后优先实现 FastAPI，或继续增强基础版 RAG 问答链，继续复用 `rag_service.py`。

---

## 常用命令速查

```bash
# 配置 Embedding
uv run python config_demo.py

# 配置 Chat LLM
uv run python llm_config_demo.py

# 入库文档（增量）
uv run python main.py --store

# 入库文档并清理已删除源文件
uv run python main.py --store --prune-deleted

# 全量重建
uv run python main.py --store --reindex

# 查询演示
uv run python query_demo.py "你的问题"

# RAG 问答演示
uv run python answer_demo.py "你的问题"

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
> 已完成基础版 RAG 问答链（检索 + LLM 生成回答）。还未做的：Web API（FastAPI）、问答链增强、增量更新优化。
>
> 关键记忆点：
> - 文本 Loader 需显式指定 `encoding="utf-8"`（Windows 兼容）
> - `vector_store/store.py` 有增量入库逻辑，入库时记录 `file_mtime` + `file_size` 指纹
> - `embedding/crud.py` 分两层 API：`f(session, ...)` 底层的和 `f(...)` 自动管理 Session 的
> - API Key 用 Fernet 加密存储在 SQLite 中
> - 所有配置常量集中在 `embedding/config.py`

---

## 2026-07-05 12:59

### 变更类型
修复 / 文档

### 变更内容
- `data_loader.load_documents()` 新增严格加载模式，用于在存在文件解析失败时中止后续处理。
- 文档加载会跳过空内容文件，避免空文档被当作成功加载。
- `rag_service.index_documents()` 在启用 `prune_deleted` 时使用严格加载，避免将临时加载失败误判为源文件已删除。
- 补充 `data_loader` 相关单元测试，覆盖空文件、仅空内容目录和严格模式加载失败。

### 影响范围
- `data_loader/loader.py`
- `rag_service.py`
- `tests/test_data_loader.py`
- `README.md`
- `CODE_NOTES.md`
- `history.md`

### 原因
- Review 发现加载失败被吞掉后，`--prune-deleted` 可能误删已有向量。
- Review 发现空内容文件会被当作成功加载，可能导致后续无有效 Chunk。

### 验证
- 已运行：`codex-runtimes ... python.exe -m compileall data_loader rag_service.py tests/test_data_loader.py`，语法编译通过。
- 未运行成功：`uv run pytest tests/test_data_loader.py`，当前 PATH 找不到 `uv`。
- 未运行成功：`.venv/Scripts/python.exe -m pytest tests/test_data_loader.py`，当前 `.venv` 的 uv trampoline 因权限拒绝无法启动。
- 未运行成功：内置 Python 缺少 `pytest`、`ruff` 和项目依赖 `langchain_core`。

### 注意事项
- 普通加载仍保持兼容，默认不因单个文件失败而中止。
- 使用 `--prune-deleted` 时，若本次扫描存在文件加载失败，会停止处理并提示错误。

---

## 2026-07-05 13:16

### 变更类型
配置 / 文档

### 变更内容
- 在 `pyproject.toml` 中新增 pytest 配置：`pythonpath = ["."]`、`testpaths = ["tests"]`。
- 在 `README.md` 开发命令中补充 `uv run pytest tests`。

### 影响范围
- `pyproject.toml`
- `README.md`
- `history.md`

### 原因
- 用户本机执行 `uv run pytest tests` 时，pytest 能启动但无法导入项目根目录模块，报 `ModuleNotFoundError: No module named 'data_loader'` 等错误。
- 将项目根目录加入 pytest 的 `pythonpath` 后，可避免每次手动设置 `PYTHONPATH`。

### 验证
- 用户终端已确认 `uv --version` 可用，版本为 `uv 0.11.16`。
- 用户终端执行 `uv run pytest tests` 已能安装测试依赖，但因 pytest import path 未配置导致收集阶段失败。
- 当前 Codex 子进程 PATH 未继承用户终端中的 `uv`，直接执行 `uv --version` 仍提示找不到命令。
- 已用 Codex 内置 Python 解析 `pyproject.toml`，确认 TOML 语法有效。

### 注意事项
- 修改后应在用户 PowerShell 中重新执行 `uv run pytest tests`。
- `Failed to hardlink files; falling back to full copy` 是 uv 缓存链接方式警告，不是测试失败原因；如需消除提示，可设置 `UV_LINK_MODE=copy`。

---

## 2026-07-05 13:45

### 变更类型
验证 / 文档

### 变更内容
- 使用用户本机 `uv.exe` 绝对路径完成测试和静态检查。
- 确认 pytest 配置已生效，测试可正常导入项目根目录模块。

### 影响范围
- `history.md`
- 测试命令：`uv run pytest tests -p no:cacheprovider`
- 检查命令：`uv run ruff check .`

### 原因
- 需要验证此前 `data_loader` 修复和 pytest `pythonpath` 配置是否正确。
- Codex 工具进程默认 PATH 不包含用户通过 pip 安装的 `uv.exe`，因此使用绝对路径运行。

### 验证
- 已通过：`uv run pytest tests -p no:cacheprovider`，共 11 个测试全部通过。
- 已通过：`uv run ruff check .`，结果为 `All checks passed!`。

### 注意事项
- pytest 命令禁用了 cacheprovider，用于避开当前 `.pytest_cache` 目录权限提示。
- 后续 Codex 运行 uv 时继续使用 `C:\Users\14428\AppData\Local\Programs\Python\Python314\Scripts\uv.exe`。

---

## 2026-07-05 14:59

### 变更类型
文档 / 验证

### 变更内容
- 更新 `PROJECT_REPORT.md`，将旧的 `uv` 不可用、pytest 未执行状态同步为当前已验证状态。
- 更新 `README.md`，补充旧版 Word `.doc` 当前不在支持范围内的说明。
- 完成收尾核查：`uv.lock` 与 `pyproject.toml` 一致，测试和 ruff 均已通过。

### 影响范围
- `PROJECT_REPORT.md`
- `README.md`
- `history.md`
- `uv.lock`
- `Data/docs`

### 原因
- 收尾确认时发现 `PROJECT_REPORT.md` 仍保留旧环境状态，容易误导后续维护。
- 当前 `Data/docs` 中存在 `.doc` 文件，但加载器只支持 `.docx`，需要在文档中明确提示。

### 验证
- 已运行：`uv lock --check`，解析 118 个包，退出码为 0。
- 已运行：`uv run pytest tests -p no:cacheprovider`，共 11 个测试全部通过。
- 已运行：`uv run ruff check .`，结果为 `All checks passed!`。
- 已运行：`git diff --check`，未发现空白错误。

### 注意事项
- `uv.lock` 当前大量删除旧包，主要是移除已不在当前依赖图中的旧解析结果；`uv lock --check` 已确认锁文件与当前配置一致。
- `Data/docs` 当前为业务资料替换状态，包含 3 个 `.doc` 文件；这些文件会被当前加载器跳过，除非后续转换为 `.docx` 或新增 `.doc` 解析支持。

---

## 2026-07-05 15:26

### 变更类型
新增 / 配置 / 文档

### 变更内容
- 新增 `rag_chain.py`，实现基础版 RAG 问答链：检索上下文拼接、Chat LLM 配置、提示词构造、答案生成和来源引用返回。
- 新增 `answer_demo.py`，提供单次问答和交互式问答入口，支持 `top_k`、相关性阈值、上下文长度限制和上下文调试输出。
- 新增 `.env.example`，用占位符说明 `RAG_LLM_*` 配置；更新 `.gitignore`，排除本机 `.env` 和 `.env.*`，保留 `.env.example`。
- 新增 `tests/test_rag_chain.py`，覆盖问答链的上下文拼接、提示词和响应转文本纯逻辑。
- 更新 `README.md`、`CODE_NOTES.md`、`PROJECT_REPORT.md`，同步 RAG 问答链用法、当前功能状态和后续规划。

### 影响范围
- `rag_chain.py`
- `answer_demo.py`
- `.env.example`
- `.gitignore`
- `tests/test_rag_chain.py`
- `README.md`
- `CODE_NOTES.md`
- `PROJECT_REPORT.md`
- `history.md`

### 原因
- 项目此前已完成文档检索，但缺少“检索结果 + LLM 生成回答”的完整 RAG 问答链。
- 通过环境变量配置 Chat LLM，可避免新增数据库 schema 和配置迁移，同时不把真实密钥写入项目文件。

### 验证
- 已运行：`uv run pytest tests/test_rag_chain.py -p no:cacheprovider`，4 个测试通过。
- 已运行：`uv run pytest tests -p no:cacheprovider`，共 15 个测试全部通过。
- 已运行：`uv run ruff check .`，结果为 `All checks passed!`。
- 已运行：`git diff --check`，退出码为 0，仅提示 Windows 行尾转换警告。

### 注意事项
- 本次验证未调用真实 LLM，也未读取或输出真实 API Key；实际问答需用户复制 `.env.example` 为 `.env` 并填写本机 LLM 配置。
- `CHANGELOG.md` 和 `docs/` 目录仍不存在；本次沿用项目现有 `history.md`、`PROJECT_REPORT.md`、`CODE_NOTES.md` 文档记录方式。

---

## 2026-07-05 16:18

### 变更类型
新增 / 配置 / 文档

### 变更内容
- 新增 `llm/` 独立模块，按 `embedding/` 的分层方式提供 Chat LLM schema、ORM、CRUD、Provider 工厂、统一 manager 和环境变量兜底。
- 新增 `llm_config_demo.py`，用户可交互式选择 OpenAI-compatible API Key 模型或本地 Ollama 模型，并将配置保存到 SQLite。
- `llm_configs` 表复用 `Data/rag.db`，API Key 复用 Fernet 加密能力，避免真实密钥进入代码、文档或日志。
- 调整 `rag_chain.py`，移除内置环境变量解析和 Provider 创建逻辑，改为通过 `llm/` 模块获取 Chat LLM。
- 调整 `answer_demo.py`，LLM 缺失时优先提示运行 `llm_config_demo.py`，`.env.example` 仅作为部署兜底。
- 新增 `tests/test_llm_schema.py`，并在 `tests/manual_logic_check.py` 中加入 LLM schema 轻量检查。
- 更新 `README.md`、`CODE_NOTES.md`、`PROJECT_REPORT.md`、`.env.example`，同步新的 LLM 配置方式。

### 影响范围
- `llm/`
- `llm_config_demo.py`
- `embedding/database.py`
- `rag_chain.py`
- `answer_demo.py`
- `tests/test_llm_schema.py`
- `tests/manual_logic_check.py`
- `README.md`
- `CODE_NOTES.md`
- `PROJECT_REPORT.md`
- `.env.example`
- `history.md`

### 原因
- 用户希望 RAG 问答链中的文本模型配置与 Embedding 配置类似，可由用户自行选择 API Key 模型或本地模型。
- 原先仅依赖 `.env` 的方式不符合项目已有配置结构，也不利于后续 GUI/Web API 复用。

### 验证
- 已运行：`uv run pytest tests/test_llm_schema.py tests/test_rag_chain.py -p no:cacheprovider`，9 个测试通过。
- 已运行：`uv run pytest tests -p no:cacheprovider`，共 20 个测试全部通过。
- 已运行：`uv run ruff check .`，结果为 `All checks passed!`。

### 注意事项
- 本次仍未调用真实 LLM，也未读取或输出真实 API Key。
- 现有 `Data/rag.db` 会在下次运行 `init_db()` 时自动创建 `llm_configs` 表；未做破坏性迁移。
- `.env.example` 仍只包含占位符，真实密钥应通过 `llm_config_demo.py` 或本机环境变量提供。

---

## 2026-07-05 17:53

### 变更类型
新增 / 配置 / 文档 / 验证

### 变更内容
- 新增 `api/` FastAPI 后端，提供健康检查、配置状态、向量库状态、文档入库、语义检索和 RAG 问答接口。
- 新增 `web/streamlit_app.py` Streamlit 控制台，通过 HTTP 连接 FastAPI 后端，提供状态、入库、检索和问答页面。
- 新增 `tests/test_api.py`，覆盖 API 健康检查、配置状态、检索响应和问答响应。
- 在 `pyproject.toml` 中新增 FastAPI、Uvicorn、Streamlit 依赖，并更新 `uv.lock`。
- 更新 `.gitignore`，排除 SQLite WAL/SHM 运行文件 `Data/rag.db-*`，避免本地数据库临时文件被误提交。
- 同步更新 `README.md`、`PROJECT_REPORT.md`、`CODE_NOTES.md` 的 Web API、页面、启动命令和当前功能说明。

### 影响范围
- `api/`
- `web/`
- `tests/test_api.py`
- `.gitignore`
- `pyproject.toml`
- `uv.lock`
- `README.md`
- `PROJECT_REPORT.md`
- `CODE_NOTES.md`
- `history.md`

### 原因
- 用户要求使用 FastAPI 和 Streamlit 写出页面并连接现有 RAG 管线，完成后测试是否可正常使用，并提交到 GitHub。
- Web 层需要复用现有 `rag_service.py` 和 `rag_chain.py`，避免重复实现业务逻辑。
- SQLite WAL 模式会产生本地运行文件，需要纳入忽略规则，降低误提交风险。

### 验证
- 已运行：`uv lock`，依赖锁文件更新成功。
- 已运行：`uv run pytest tests -p no:cacheprovider`，共 24 个测试通过。
- 已运行：`uv run ruff check .`，结果为 `All checks passed!`。
- 已运行 FastAPI 后端，并检查 `/health` 返回正常状态。
- 已检查 `/config/status` 可返回 Embedding/LLM 配置状态，响应不包含密钥。
- 已运行 Streamlit 页面，首页 HTTP 访问返回 200。

### 注意事项
- `CHANGELOG.md` 和 `docs/` 目录仍不存在；本次继续沿用项目现有 `history.md`、`README.md`、`PROJECT_REPORT.md`、`CODE_NOTES.md` 文档体系。
- 实际 RAG 问答仍依赖用户先配置 Embedding、配置 Chat LLM，并完成文档入库。
- 本次未提交 `Data/docs` 业务资料变更，也未提交 `Data/rag.db-*` 本地运行文件。
