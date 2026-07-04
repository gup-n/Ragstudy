# 代码说明索引

> 生成时间：2026-07-05
> 用途：为每份代码提供简要注释，说明整体功能、主要方法和关键变量。

---

## 根目录脚本

### `main.py`

整体功能：项目主入口，提供管线检查、文档入库和语义检索三类命令行模式。

主要方法：
- `parse_args()`：解析命令行参数，并校验 `top_k`、分数阈值和清理参数。
- `_print_embedding_config_help()`：输出 Embedding 未配置时的引导信息。
- `_get_embeddings()`：获取 Embedding 实例，失败时统一退出。
- `cmd_pipeline()`：执行加载、切割和可选 Embedding 验证。
- `cmd_store()`：执行文档入库，支持增量、全量重建和已删除文件清理。
- `cmd_query()`：执行语义检索并展示结果和相关性分数。
- `_print_summary()`：输出文档数和 Chunk 数摘要。
- `main()`：根据参数选择运行模式。

关键变量：
- `args.store`：是否执行入库模式。
- `args.query`：查询文本，存在时进入检索模式。
- `args.recursive`：是否递归扫描文档目录。
- `args.prune_deleted`：是否清理已删除源文件的旧向量。
- `args.score_threshold`：最低相关性分数阈值。

### `query_demo.py`

整体功能：无需 LLM 的语义检索演示脚本，支持单次查询和交互式查询。

主要方法：
- `print_banner()`：打印查询演示标题。
- `print_result()`：格式化展示单条检索结果。
- `_print_config_error()`：展示 Embedding 缺失时的配置提示。
- `demo()`：执行一次查询并展示向量库状态和检索结果。
- `interactive_mode()`：循环读取用户问题并检索。
- `main()`：解析参数并选择单次或交互模式。

关键变量：
- `query`：用户查询文本。
- `top_k`：返回片段数量。
- `score_threshold`：最低相关性分数阈值。
- `emb`：复用的 Embedding 实例。
- `retrieval`：服务层返回的检索结果对象。

### `config_demo.py`

整体功能：交互式 Embedding Provider 配置向导。

主要方法：
- `print_banner()`：打印配置向导标题。
- `choose_provider()`：让用户选择 Provider。
- `input_value()`：读取带默认值的配置项。
- `collect_config()`：根据 Provider 收集参数并生成配置对象。
- `verify_embedding()`：用测试文本验证配置是否可用。
- `main()`：执行初始化、选择、填写、保存、验证流程。

关键变量：
- `PROVIDER_INFO`：Provider 展示信息和字段定义。
- `provider_id`：用户选择的 Provider 标识。
- `config`：待保存的 Embedding 配置。
- `kwargs`：收集到的配置字段。

### `rag_service.py`

整体功能：RAG 管线服务层，为 CLI、演示脚本和未来 Web API 提供统一业务接口。

主要类型：
- `ConfigurationError`：配置缺失或不可用时抛出的异常。
- `PipelineResult`：加载和切割结果。
- `EmbeddingValidationResult`：Embedding 验证结果。
- `IndexResult`：入库结果。
- `VectorStoreStats`：向量库统计信息。
- `RetrievalResult`：检索结果。

主要方法：
- `get_embeddings_or_raise()`：初始化数据库并获取当前启用的 Embedding。
- `load_and_split()`：加载文档并切割为 Chunks。
- `validate_embedding()`：用少量 Chunk 验证 Embedding 可用性。
- `index_documents()`：加载、切割并写入向量库。
- `get_vector_store_stats()`：读取向量库文件数和 Chunk 数。
- `retrieve()`：执行语义检索并返回文档、分数和统计。

关键变量：
- `directory`：文档目录。
- `splitter`：切割策略。
- `recursive`：是否递归扫描。
- `reindex`：是否全量重建。
- `prune_deleted`：是否清理已删除源文件。
- `include_scores`：是否返回相关性分数。

---

## 文档加载模块

### `data_loader/config.py`

整体功能：集中维护文档目录、加载器映射和加载参数。

主要类型：
- `SimpleMarkdownLoader`：基于 TextLoader 的轻量 Markdown 加载器。
- `SimpleDocxLoader`：基于 `python-docx` 的轻量 DOCX 加载器。

主要方法：
- `SimpleDocxLoader.load()`：读取 DOCX 段落和表格文本，返回 LangChain Document。

关键变量：
- `DOCUMENT_DIR`：默认文档目录，当前为 `Data/docs`。
- `LOADER_MAPPING`：文件扩展名到 Loader 的映射。
- `LOADER_ARGS`：不同 Loader 的额外参数。

### `data_loader/loader.py`

整体功能：扫描文档目录，按扩展名加载文件，并补全 metadata。

主要方法：
- `get_loader_for_file()`：根据文件扩展名创建对应 Loader。
- `_iter_files()`：根据递归配置枚举文件。
- `_build_source_metadata()`：生成稳定文件 metadata。
- `load_documents()`：加载目录中的所有支持文档。
- `_print_summary()`：输出加载摘要。

关键变量：
- `SUPPORTED_EXTENSIONS`：支持的文件扩展名集合。
- `dir_path`：解析后的文档目录。
- `all_documents`：所有加载成功的 Document。
- `loaded_files`：加载成功的文件统计。
- `skipped_files`：跳过或加载失败的文件。

### `data_loader/__init__.py`

整体功能：延迟导出加载模块能力，减少模块运行时的循环导入风险。

主要方法：
- `__getattr__()`：首次访问导出名称时再导入 `data_loader.loader`。

关键变量：
- `__all__`：对外公开的函数和常量名称。

---

## 文本切割模块

### `data_splitter/config.py`

整体功能：集中维护文本切割策略和默认参数。

关键变量：
- `DEFAULT_SPLITTER`：默认切割策略，当前为 `recursive`。
- `SPLITTER_MAPPING`：策略名称到切割器类的映射。
- `SPLITTER_ARGS`：每种切割器的默认参数。

### `data_splitter/splitter.py`

整体功能：将 Document 列表切割为 Chunks，并补充 Chunk metadata。

主要方法：
- `get_text_splitter()`：根据策略名称创建切割器。
- `split_documents()`：执行文本切割。
- `_annotate_chunks()`：为每个 Chunk 写入 `chunk_index` 和 `chunk_id`。
- `_print_summary()`：输出切割摘要。

关键变量：
- `SUPPORTED_SPLITTERS`：支持的切割策略集合。
- `splitter_type`：当前切割策略。
- `split_docs`：切割后的 Chunk 列表。
- `counters`：按 `source_id` 统计 Chunk 序号。

### `data_splitter/__init__.py`

整体功能：延迟导出切割模块能力。

主要方法：
- `__getattr__()`：首次访问导出名称时再导入 `data_splitter.splitter`。

关键变量：
- `__all__`：对外公开的函数和常量名称。

---

## Embedding 模块

### `embedding/config.py`

整体功能：集中维护项目路径、数据库路径、加密密钥路径和本地缓存路径。

关键变量：
- `PROJECT_ROOT`：项目根目录。
- `DATA_DIR`：数据目录。
- `DATABASE_PATH`：SQLite 数据库路径。
- `ENABLE_SQLITE_WAL`：是否启用 SQLite WAL。
- `ENCRYPTION_KEY_PATH`：Fernet 密钥文件路径。
- `HF_MODEL_CACHE_DIR`：HuggingFace 模型缓存目录。
- `OLLAMA_DEFAULT_BASE_URL`：Ollama 默认服务地址。

### `embedding/schema.py`

整体功能：定义 Embedding 配置的数据模型和异常类型。

主要类型：
- `ProviderName`：支持的 Provider 名称集合。
- `EmbeddingConfigBase`：配置基础字段。
- `EmbeddingConfigCreate`：新增配置模型。
- `EmbeddingConfigUpdate`：更新配置模型。
- `EmbeddingConfig`：运行时配置模型。
- `EmbeddingConfigRead`：数据库读取模型。
- `EmbeddingError` 及其子类：Embedding 模块异常。

主要方法：
- `clean_model()`：校验模型名称非空。
- `clean_api_key()`：清理 API Key 前后空白。

关键变量：
- `provider`：Provider 类型。
- `model`：Embedding 模型名称。
- `base_url`：服务地址。
- `api_key`：可选密钥。
- `extra`：Provider 特定附加参数。

### `embedding/models.py`

整体功能：定义 SQLAlchemy ORM 模型。

主要类型：
- `Base`：ORM 基类。
- `EmbeddingConfigModel`：Embedding 配置表。

关键变量：
- `id`：主键。
- `provider`：Provider 类型。
- `model`：模型名称。
- `base_url`：服务地址。
- `api_key`：加密后的密钥。
- `enabled`：是否启用。
- `extra`：JSON 字符串形式的额外配置。
- `created_at`、`updated_at`：创建和更新时间。

### `embedding/database.py`

整体功能：管理 SQLite Engine、Session 和数据库初始化。

主要方法：
- `configure_sqlite()`：设置 SQLite 连接参数。
- `init_db()`：创建数据库表。
- `get_session()`：提供事务型 Session 上下文。
- `close_db()`：释放数据库连接池。

关键变量：
- `engine`：SQLAlchemy 引擎。
- `SessionLocal`：Session 工厂。

### `embedding/crud.py`

整体功能：提供 Embedding 配置的增删改查，并处理 API Key 加密解密。

主要方法：
- `_get_cipher()`：获取 Fernet 加密器。
- `_load_or_create_key()`：读取或创建加密密钥。
- `_dump_extra()`、`_load_extra()`：处理 extra JSON。
- `encrypt_api_key()`、`decrypt_api_key()`：加密和解密 API Key。
- `_orm_to_read()`：ORM 对象转读取模型。
- `create_config()`：新增配置。
- `update_config()`：更新配置。
- `get_config()`：按 id 读取配置。
- `list_configs()`：列出配置。
- `set_enabled()`：启用或停用配置。
- `has_enabled_config()`：检查是否有启用配置。
- `save_config()`、`get_enabled_config()`、`delete_config()`：自动管理 Session 的便捷函数。

关键变量：
- `ENCRYPTION_KEY_PATH`：密钥文件路径。
- `fields_set`：更新请求中实际传入的字段集合。
- `orm_row`：数据库中的配置记录。

### `embedding/providers.py`

整体功能：维护 Provider 工厂函数注册表。

主要方法：
- `_create_huggingface()`：创建 HuggingFace Embeddings。
- `_create_ollama()`：创建 Ollama Embeddings。
- `_create_openai_compatible()`：创建 OpenAI-Compatible Embeddings。

关键变量：
- `ProviderFactory`：Provider 工厂函数类型。
- `PROVIDERS`：Provider 名称到工厂函数的映射。
- `model_kwargs`、`encode_kwargs`：HuggingFace 参数。
- `kwargs`：Provider 初始化参数。

### `embedding/factory.py`

整体功能：根据运行时配置创建 Embeddings 实例。

主要方法：
- `create_embeddings()`：查找 Provider 工厂并创建 Embeddings。

关键变量：
- `provider`：归一化后的 Provider 名称。
- `factory`：Provider 工厂函数。

### `embedding/manager.py`

整体功能：Embedding 模块对外统一入口。

主要方法：
- `get_embedding()`：读取启用配置并创建 Embedding 实例。

关键变量：
- `config`：当前启用的 Embedding 配置。

### `embedding/downloader.py`

整体功能：下载并检查 HuggingFace 模型缓存。

主要方法：
- `_resolve_cache_dir()`：解析缓存目录。
- `_ensure_dir()`：确保目录存在。
- `download_huggingface_model()`：下载模型快照。
- `is_model_downloaded()`：检查模型是否已在本地缓存。

关键变量：
- `model_name`：模型仓库名。
- `cache_dir`：缓存目录。
- `target_dir`：最终缓存目录。
- `local_path`：下载后的本地路径。

### `embedding/__init__.py`

整体功能：集中导出 Embedding 模块公共 API。

关键变量：
- `__all__`：模块公开接口清单。

---

## 向量库模块

### `vector_store/config.py`

整体功能：集中维护 ChromaDB 持久化配置。

关键变量：
- `CHROMA_PERSIST_DIR`：向量库持久化目录。
- `CHROMA_COLLECTION_NAME`：默认 Collection 名称。
- `DEFAULT_TOP_K`：默认检索数量。

### `vector_store/store.py`

整体功能：负责 ChromaDB 入库、增量更新、删除、检索和统计。

主要方法：
- `_get_store()`：创建或加载 ChromaDB 实例。
- `_hash_file()`：计算文件内容哈希。
- `_get_file_fingerprint()`：获取文件 mtime、size 和内容哈希。
- `_get_source_id()`：获取 Chunk 的稳定源文件身份。
- `_enrich_metadata()`：补充文件指纹 metadata。
- `_ensure_chunk_ids()`：确保每个 Chunk 有稳定 id。
- `_group_by_source_id()`：按文件身份分组。
- `_fingerprint_matches()`：判断文件是否未变化。
- `get_stored_file_index()`：读取向量库中的文件指纹索引。
- `delete_by_source_ids()`：按 source_id 删除向量。
- `delete_by_filenames()`：按文件名删除向量，兼容旧调用。
- `add_to_store()`：增量入库。
- `force_reindex()`：全量重建。
- `search()`：检索并返回文档。
- `search_with_scores()`：检索并返回文档和相关性分数。
- `get_retriever()`：返回 LangChain Retriever。
- `count_documents()`：统计向量数量。
- `get_file_list()`：列出已入库文件。
- `delete_all()`：清空向量库。

关键变量：
- `_META_SOURCE_ID`：文件稳定身份字段。
- `_META_DOC_ROOT`：文档根目录字段。
- `_META_MTIME`：文件修改时间字段。
- `_META_SIZE`：文件大小字段。
- `_META_CONTENT_HASH`：内容哈希字段。
- `_META_CHUNK_ID`：Chunk 身份字段。
- `to_add`：本次需要入库的 Chunk。
- `to_delete`：本次需要删除的文件身份。
- `skipped`：本次跳过的 Chunk 数。
- `stored_index`：向量库中已有文件指纹索引。

### `vector_store/__init__.py`

整体功能：集中导出向量库模块公共 API。

关键变量：
- `__all__`：模块公开接口清单。

---

## 测试代码

### `tests/test_data_loader.py`

整体功能：验证文档加载递归扫描和 metadata 写入。

主要方法：
- `test_load_documents_recurses_and_sets_source_metadata()`：验证递归加载和 source metadata。
- `test_load_documents_can_scan_first_level_only()`：验证关闭递归后只扫描第一层。

关键变量：
- `tmp_path`：临时测试目录。
- `docs_dir`：测试文档根目录。
- `source_ids`：加载结果中的文件身份集合。

### `tests/test_splitter.py`

整体功能：验证文本切割后的 Chunk metadata。

主要方法：
- `test_split_documents_adds_stable_chunk_metadata()`：验证 `chunk_index` 和 `chunk_id`。

关键变量：
- `text`：构造的长文本。
- `docs`：输入 Document 列表。
- `chunks`：切割结果。

### `tests/test_vector_store_metadata.py`

整体功能：验证向量库 metadata 相关纯函数。

主要方法：
- `test_ensure_chunk_ids_uses_source_id_and_chunk_index()`：验证稳定 Chunk id。
- `test_group_by_source_id_keeps_same_filenames_separate()`：验证同名文件不会冲突。
- `test_fingerprint_prefers_content_hash()`：验证内容哈希优先级。

关键变量：
- `chunks`：测试 Chunk 列表。
- `ids`：生成的 Chunk id。
- `groups`：按 source_id 分组结果。
- `stored`、`current`：模拟的新旧文件指纹。

### `tests/test_embedding_schema.py`

整体功能：验证 Embedding 配置模型校验。

主要方法：
- `test_embedding_config_rejects_empty_model()`：空模型名应校验失败。
- `test_embedding_config_accepts_supported_provider()`：支持的 Provider 可创建配置。

关键变量：
- `config`：合法的 Embedding 配置对象。

### `tests/manual_logic_check.py`

整体功能：在没有 pytest 命令时执行轻量冒烟检查，覆盖核心纯逻辑。

主要方法：
- `check_data_loader()`：检查递归加载、一级扫描和 source metadata。
- `check_splitter()`：检查 Chunk 序号和 Chunk 身份。
- `check_vector_metadata()`：检查向量 metadata 纯函数。
- `check_embedding_schema()`：检查 Embedding 配置校验。
- `main()`：依次执行所有检查。

关键变量：
- `docs_dir`：临时文档目录。
- `source_ids`：加载后的文件身份集合。
- `chunks`：用于检查的 Chunk 列表。
- `stored`、`current`：模拟的新旧文件指纹。
