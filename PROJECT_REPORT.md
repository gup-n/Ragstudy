# RAG 项目交付说明

> 生成时间：2026-07-05
> 范围：本次对话内的代码优化、文档整理、测试记录和后续规划

---

## 一、本次对话完成的操作

### 1. 项目结构优化
- 新增 `rag_service.py` 服务层，将加载、切割、入库、检索等业务逻辑从命令行入口中抽离。
- `main.py` 和 `query_demo.py` 改为调用服务层，减少重复逻辑。
- 删除空文件 `embedding/Setting.json`，避免误导配置来源。

### 2. 文档加载优化
- `Data/Docs` 统一改为 `Data/docs`，提升跨平台一致性。
- 文档加载默认递归扫描子目录。
- 每个文档写入稳定 metadata：`source`、`doc_root`、`relative_path`、`source_id`、`filename`、`file_ext`。
- PDF 读取改为轻量 `PyPDFLoader`。
- DOCX 读取改为基于 `python-docx` 的轻量加载器，读取段落和表格文本。

### 3. 文本切割优化
- 切割后的每个 Chunk 自动写入 `chunk_index` 和 `chunk_id`。
- `chunk_id` 基于 `source_id` 和序号生成，便于后续覆盖更新、引用和排查。

### 4. 向量库存储优化
- 增量入库从按 `filename` 判断升级为按 `source_id` 判断，避免同名文件冲突。
- 文件指纹从 `mtime + size` 升级为 `content_hash + mtime + size`。
- 新增 `delete_by_source_ids()`，支持按稳定文件身份删除旧向量。
- 新增 `search_with_scores()`，支持返回相关性分数。
- `main.py --store --prune-deleted` 支持清理本次扫描目录中已删除源文件的旧向量。

### 5. Embedding 配置优化
- Provider 限制为三类：`huggingface`、`ollama`、`openai-compatible`。
- 模型名称增加非空校验。
- 配置更新支持清空可选字段，如 `base_url`、`api_key`、`extra`。
- 配置向导的 API Key 输入改为隐藏输入。

### 6. 命令行能力优化
- `main.py` 新增 `--recursive`、`--no-recursive`、`--score-threshold`、`--prune-deleted`。
- `query_demo.py` 新增 `--score-threshold`，并展示相关性分数。
- 交互查询模式复用同一个 Embedding 实例，避免重复初始化。

### 7. 文档和测试
- 更新 `README.md` 和 `history.md`。
- 新增 `tests/`，覆盖文档加载、切割 metadata、向量 metadata、Embedding schema 校验。
- 新增本文件和 `CODE_NOTES.md`，用于交付说明和逐文件代码说明。

### 8. RAG 问答链
- 新增 `rag_chain.py`，复用服务层检索结果，完成上下文拼接、提示词构造、Chat LLM 调用和来源引用返回。
- 新增 `answer_demo.py`，支持单次问答、交互式问答、相关性阈值、上下文长度限制和调试上下文输出。
- 新增 `llm/` 模块，按 `embedding/` 的结构提供 Chat LLM schema、ORM、CRUD、Provider 工厂和统一 manager。
- 新增 `llm_config_demo.py`，支持用户自行选择 OpenAI-compatible API Key 模型或本地 Ollama 模型。
- 新增 `.env.example`，提供 `RAG_LLM_*` 环境变量兜底占位符示例；真实密钥只应写入本机配置或环境变量。
- 更新 `.gitignore`，排除本机 `.env` 和 `.env.*`，保留 `.env.example`。
- 新增 `tests/test_rag_chain.py` 和 `tests/test_llm_schema.py`，覆盖问答链与 LLM 配置纯逻辑。

### 9. FastAPI 与 Streamlit 页面
- 新增 `api/`，暴露健康检查、配置状态、向量库状态、文档入库、语义检索和 RAG 问答接口。
- 新增 `web/streamlit_app.py`，提供状态、入库、检索、问答四个页面。
- Streamlit 通过 HTTP 连接 FastAPI，业务逻辑仍集中复用 `rag_service.py` 和 `rag_chain.py`。
- 新增 `tests/test_api.py`，覆盖核心 API 契约。
- 新增依赖 `fastapi`、`uvicorn[standard]`、`streamlit`，并更新 `uv.lock`。

---

## 二、当前项目具备的功能

### 1. 文档处理
- 支持 TXT、Markdown、PDF、DOCX。
- 默认读取 `Data/docs`。
- 支持递归扫描目录。
- 自动跳过不支持的文件类型。

### 2. 文本切割
- 支持 `recursive` 和 `character` 两种切割策略。
- 默认 `recursive`。
- 默认 Chunk 大小为 800，重叠为 150。
- 支持中文标点作为递归切割分隔符。

### 3. Embedding 配置管理
- 支持 HuggingFace、Ollama、OpenAI-Compatible 三类 Provider。
- 配置存储在 SQLite。
- API Key 使用 Fernet 加密存储。
- 同一时间仅允许一个启用配置。

### 4. 向量存储和检索
- 使用 ChromaDB 持久化向量。
- 支持增量入库。
- 支持全量重建。
- 支持按文件身份删除旧向量。
- 支持清理已删除源文件的旧向量。
- 支持语义检索和带分数检索。

### 5. 命令行入口
- `config_demo.py`：交互式配置 Embedding。
- `main.py`：管线检查、入库、检索。
- `query_demo.py`：单次或交互式语义检索演示。
- `llm_config_demo.py`：交互式配置 Chat LLM。
- `answer_demo.py`：单次或交互式 RAG 问答演示。

### 6. 可复用服务层
- `rag_service.py` 提供加载切割、入库、统计、检索等函数。
- 后续 FastAPI 可以直接复用服务层。

### 7. RAG 问答链
- `rag_chain.py` 提供检索上下文拼接、Chat LLM 配置和问答生成。
- `answer_demo.py` 提供单次和交互式问答入口。
- 支持 OpenAI-compatible 和 Ollama Chat LLM。
- 支持通过 `llm_config_demo.py` 将 LLM 配置加密保存到 SQLite。
- 数据库未启用 LLM 配置时，可读取 `RAG_LLM_*` 环境变量作为兜底。
- 答案会返回引用来源编号、文件名、`chunk_id` 和相关性分数。

### 8. Web API 和页面
- `api/app.py` 提供 FastAPI 后端。
- `web/streamlit_app.py` 提供 Streamlit 控制台。
- 页面包含状态、入库、检索和问答 Tab。
- API 状态接口不会返回 API Key 或其他真实密钥。

---

## 三、未完成部分和规划

### P0：环境锁文件和测试运行（已完成）
- 已使用用户本机 `uv.exe` 绝对路径完成验证。
- `uv.lock` 已通过 `uv lock --check`，当前与 `pyproject.toml` 保持一致。
- `uv run pytest tests -p no:cacheprovider` 已通过，共 24 个测试。
- `uv run ruff check .` 已通过。

### P1：完整 RAG 问答链（基础版已完成）
- 已新增 `rag_chain.py` 和 `answer_demo.py`，可执行检索 + LLM 生成回答。
- 已新增 `llm/` 配置模块和 `llm_config_demo.py`，用户可选择 API Key 模型或本地 Ollama 模型。
- `.env` 仅作为部署兜底，不再是唯一配置方式。
- 后续可继续完善：多轮对话、引用去重、上下文压缩和失败重试。

### P1：FastAPI Web API 和 Streamlit 页面（基础版已完成）
- 已新增 FastAPI 后端和 Streamlit 控制台。
- 已暴露文档入库、检索、问答、配置状态和向量库统计接口。
- 后续可继续完善鉴权、任务队列、长任务进度、异步入库和更细粒度配置管理。

### P2：更强的检索质量
- 可加入 MMR 检索。
- 可加入 metadata filter。
- 可加入重排序模型。
- 可加入引用去重和上下文压缩。

### P2：配置管理完善
- Embedding 配置已有数据库管理。
- 后续可为 LLM 单独建立配置表。
- 可增加配置列表、启用、删除的 CLI 命令。

### P3：文档解析增强
- PDF 当前适合文本型 PDF。
- 扫描件 OCR 尚未支持。
- DOCX 当前读取段落和表格文本，复杂格式暂不还原。
- 旧版 Word `.doc` 当前不在支持格式内，会被加载器跳过；如需入库需转换为 `.docx` 或新增 `.doc` 解析支持。

---

## 四、额外依赖说明和安装方法

### 1. 基础依赖
项目运行依赖写在 `pyproject.toml`。

安装方式：

```bash
uv sync
```

### 2. 开发和测试依赖
测试和代码检查依赖在 `dependency-groups.dev`。

安装方式：

```bash
uv sync --group dev
```

### 3. 需要关注的依赖映射

| 代码位置 | 依赖 | 用途 |
|---|---|---|
| `data_loader/config.py` | `langchain-community`、`pypdf`、`python-docx` | TXT、MD、PDF、DOCX 加载 |
| `data_splitter/config.py` | `langchain-text-splitters` | 文本切割 |
| `embedding/providers.py` | `langchain-huggingface`、`langchain-ollama`、`langchain-openai` | 创建 Embedding 实例 |
| `llm/providers.py` | `langchain-openai`、`langchain-ollama` | 创建 Chat LLM 实例 |
| `embedding/downloader.py` | `huggingface-hub` | 下载 HuggingFace 模型 |
| `embedding/crud.py` | `sqlalchemy`、`cryptography`、`pydantic` | 配置存储、加密、校验 |
| `llm/crud.py` | `sqlalchemy`、`cryptography`、`pydantic` | LLM 配置存储、加密、校验 |
| `vector_store/store.py` | `langchain-chroma` | ChromaDB 持久化和检索 |
| `llm/env.py` | `python-dotenv` | LLM 环境变量兜底 |
| `api/app.py` | `fastapi`、`uvicorn` | Web API 后端 |
| `web/streamlit_app.py` | `streamlit` | RAG 控制台页面 |
| `tests/` | `pytest` | 单元测试 |
| 代码检查 | `ruff` | 静态检查 |

### 4. 依赖变更后的推荐命令

```bash
uv lock
uv sync --group dev
uv run pytest tests
uv run ruff check .
```

### 5. 当前环境注意事项
- Codex 工具进程默认 PATH 不包含用户通过 pip 安装的 `uv.exe`。
- 后续在 Codex 工具中运行 uv 时使用绝对路径：`C:\Users\14428\AppData\Local\Programs\Python\Python314\Scripts\uv.exe`。
- pytest 命令可加 `-p no:cacheprovider`，用于避开当前 `.pytest_cache` 目录权限提示。

---

## 五、测试前状态记录

### 已完成的检查
- 已完成源码阅读。
- 已完成主要优化实现。
- 已完成基础测试文件编写。
- 已完成依赖声明补齐。

### 已补充执行的检查
- `uv lock --check`：通过。
- `uv run pytest tests -p no:cacheprovider`：通过，共 24 个测试。
- `uv run ruff check .`：通过。

---

## 六、新会话快速开始 Prompt

请接着维护这个 RAG 项目。项目路径是 `F:\coding\python\project\RAG`，仓库是 `https://github.com/gup-n/Ragstudy.git`。

当前项目已经完成文档加载、文本切割、Embedding 配置、ChromaDB 向量存储、增量入库、带分数语义检索、服务层抽象、基础 RAG 问答链、FastAPI 后端和 Streamlit 页面。核心服务层在 `rag_service.py`。CLI 入口包括 `main.py`、`query_demo.py`、`answer_demo.py`、`config_demo.py`、`llm_config_demo.py`；Web 入口包括 `api/app.py` 和 `web/streamlit_app.py`。
当前也已具备基础 RAG 问答链：`rag_chain.py` 负责检索上下文拼接和 LLM 调用，`answer_demo.py` 提供单次/交互式问答入口，`llm/` 和 `llm_config_demo.py` 负责 Chat LLM 配置管理；`.env.example` 中的 `RAG_LLM_*` 仅作为部署兜底示例。

关键设计：
- 文档目录为 `Data/docs`。
- 文档默认递归扫描。
- 文件身份使用 `source_id`，来源于相对路径。
- Chunk 身份使用 `chunk_id`。
- 增量入库使用 `content_hash + mtime + size`。
- 已删除文件清理命令是 `uv run python main.py --store --prune-deleted`。
- 检索分数由 `search_with_scores()` 返回。
- API Key 加密存储在 SQLite 中。

尚未完成：
- 需要按需求增强 `.doc`、OCR 和检索质量。
- 可继续增强问答链的多轮对话、引用去重和上下文压缩。
- 可继续增强 Web 侧鉴权、任务进度和异步入库。

请先运行：

```bash
uv sync --group dev
uv run pytest tests
uv run ruff check .
```

如果继续开发，优先增强 Web 侧鉴权、任务进度或异步入库，继续复用 `rag_service.py`。

---

## 七、测试后复盘记录

### 1. 测试后确认本次完成的操作
- 完成项目架构整理，新增服务层 `rag_service.py`。
- 完成文档加载增强，支持递归扫描和稳定 `source_id`。
- 完成切割 metadata 增强，支持稳定 `chunk_id`。
- 完成向量库增量逻辑增强，支持内容哈希、按 `source_id` 删除和已删除源文件清理。
- 完成带分数检索能力，CLI 和查询演示均可展示分数。
- 完成 Embedding 配置校验和隐藏式 API Key 输入。
- 完成依赖声明补齐。
- 完成 `PROJECT_REPORT.md`、`CODE_NOTES.md`、`history.md` 的整理。
- 完成代码注释补充，重点解释非显而易见的设计边界。
- 新增 `tests/manual_logic_check.py`，用于没有 pytest 时做轻量逻辑检查。

### 2. 测试后确认当前项目功能
- 可加载 TXT、MD、PDF、DOCX。
- 可递归扫描文档目录。
- 可切割文档并生成稳定 Chunk 身份。
- 可配置 HuggingFace、Ollama、OpenAI-Compatible 三类 Embedding。
- 可增量写入 ChromaDB。
- 可全量重建向量库。
- 可清理已删除源文件的旧向量。
- 可执行语义检索并返回相关性分数。
- 可通过服务层复用管线能力。
- 可配置 Chat LLM，并执行带引用来源的 RAG 问答。
- 可通过 FastAPI 暴露状态、入库、检索和问答接口。
- 可通过 Streamlit 控制台连接 FastAPI 使用入库、检索和问答功能。
- 可通过 pytest、ruff 和手动检查脚本验证核心逻辑。

### 3. 测试后确认未完成部分
- RAG 问答链基础版已实现，LLM 配置管理已具备基础能力，后续可增强多轮对话、引用去重和上下文压缩。
- FastAPI Web API 和 Streamlit 页面基础版已实现，后续可增强鉴权、任务进度和异步入库。
- 检索增强能力如 MMR、metadata filter、重排序尚未实现。
- OCR、旧版 Word `.doc`、复杂 DOCX 格式还原尚未实现。

### 4. 测试后依赖安装建议

推荐在开发机器上执行：

```bash
uv lock
uv sync --group dev
uv run pytest tests
uv run ruff check .
```

如果只运行项目功能：

```bash
uv sync
```

如果需要下载 HuggingFace 模型，请确认 `huggingface-hub` 已安装。该依赖已经写入 `pyproject.toml`。

### 5. 本次实际执行的检查
- Python 语法编译：通过。
- Ruff 静态检查：通过。
- Git 空白检查：通过。
- 手动逻辑检查：通过，输出为 `manual logic checks passed`。
- `uv lock --check`：通过，解析 118 个包。
- `uv run pytest tests -p no:cacheprovider`：通过，共 24 个测试。
- `uv run ruff check .`：通过，输出为 `All checks passed!`。
- FastAPI `/health`：通过，返回 `{"status":"ok","service":"rag-api"}`。
- FastAPI `/config/status`：通过，能返回 Embedding/LLM 配置状态且不包含密钥。
- Streamlit 首页：通过，返回 HTTP 200。

### 6. 当前环境限制
- Codex 工具进程不会自动继承用户终端 PATH，直接运行 `uv` 可能找不到命令。
- 使用用户本机 `uv.exe` 绝对路径并授权后，可以正常运行测试和静态检查。

### 7. 测试后新会话 Prompt

请继续维护 `F:\coding\python\project\RAG`。当前项目已经完成一轮重构和测试后整理。服务层在 `rag_service.py`，当前入口脚本是 `main.py`、`query_demo.py`、`config_demo.py`。

当前能力包括：递归文档加载、稳定 `source_id`、稳定 `chunk_id`、Embedding 配置管理、ChromaDB 增量入库、内容哈希判断、已删除文件清理、带分数语义检索、代码说明文档和轻量逻辑检查。

请优先执行：

```bash
uv lock
uv sync --group dev
uv run pytest tests
uv run ruff check .
```

环境验证已完成。随后优先增强 Web 侧鉴权、任务进度或异步入库，或继续增强基础版 RAG 问答链。
