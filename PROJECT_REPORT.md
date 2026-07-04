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

### 6. 可复用服务层
- `rag_service.py` 提供加载切割、入库、统计、检索等函数。
- 后续 FastAPI 可以直接复用服务层。

---

## 三、未完成部分和规划

### P0：补齐环境锁文件和测试运行
- 当前 `pyproject.toml` 已更新依赖声明，但 `uv.lock` 尚未更新。
- 原因：当前环境中 `uv` 不在 PATH。
- 规划：
  1. 安装或恢复 `uv`。
  2. 执行 `uv lock`。
  3. 执行 `uv sync --group dev`。
  4. 执行 `uv run pytest tests`。

### P1：完整 RAG 问答链
- 当前项目已经完成检索，但还没有 LLM 生成回答。
- 规划：
  1. 新增 `llm` 或 `rag_chain` 模块。
  2. 增加 Chat LLM 配置。
  3. 将检索结果拼接为上下文。
  4. 输出答案、引用片段和来源。

### P1：FastAPI Web API
- 当前没有 Web 服务接口。
- 规划：
  1. 新增 `api/` 目录。
  2. 暴露文档入库、查询、配置检查、向量库统计接口。
  3. 复用 `rag_service.py`，不重复业务逻辑。

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
| `embedding/downloader.py` | `huggingface-hub` | 下载 HuggingFace 模型 |
| `embedding/crud.py` | `sqlalchemy`、`cryptography`、`pydantic` | 配置存储、加密、校验 |
| `vector_store/store.py` | `langchain-chroma` | ChromaDB 持久化和检索 |
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
- 当前终端找不到 `uv`。
- 当前项目虚拟环境中有 `ruff`，但没有 `pytest`。
- 因此本次可以运行 `ruff`，但不能直接运行 `pytest`。

---

## 五、测试前状态记录

### 已完成的检查
- 已完成源码阅读。
- 已完成主要优化实现。
- 已完成基础测试文件编写。
- 已完成依赖声明补齐。

### 待执行的检查
- Python 语法编译检查。
- Ruff 静态检查。
- Git 空白检查。
- 如果环境具备测试工具，则运行单元测试。

---

## 六、新会话快速开始 Prompt

请接着维护这个 RAG 项目。项目路径是 `F:\coding\python\project\RAG`，仓库是 `https://github.com/gup-n/Ragstudy.git`。

当前项目已经完成文档加载、文本切割、Embedding 配置、ChromaDB 向量存储、增量入库、带分数语义检索和服务层抽象。核心服务层在 `rag_service.py`。入口脚本包括 `main.py`、`query_demo.py`、`config_demo.py`。

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
- 需要更新 `uv.lock`。
- 需要安装开发依赖并运行 `pytest`。
- 需要实现完整 RAG 问答链。
- 需要实现 FastAPI Web API。

请先运行：

```bash
uv sync --group dev
uv run pytest tests
uv run ruff check .
```

如果继续开发，优先实现 RAG 问答链或 FastAPI，并复用 `rag_service.py`。

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
- 可通过手动检查脚本验证核心逻辑。

### 3. 测试后确认未完成部分
- `uv.lock` 仍需在具备 `uv` 的环境中更新。
- `pytest` 需要通过 `uv sync --group dev` 安装后再运行。
- 完整 RAG 问答链尚未实现。
- FastAPI Web API 尚未实现。
- 检索增强能力如 MMR、metadata filter、重排序尚未实现。
- OCR、复杂 DOCX 格式还原尚未实现。

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

### 6. 本次未能执行的检查
- `pytest tests` 未执行。
- 原因：当前虚拟环境没有 `pytest` 命令，当前终端也找不到 `uv`。
- 处理：已将 `pytest` 加入开发依赖组，并新增 `tests/manual_logic_check.py` 作为临时冒烟检查。

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

随后优先实现完整 RAG 问答链，或基于 `rag_service.py` 实现 FastAPI Web API。
