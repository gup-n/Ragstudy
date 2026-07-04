"""RAG 文档处理管线 — 端到端入口。

操作模式：

  1. 管线模式（默认）
     uv run python main.py
     uv run python main.py --dir Data/docs --splitter recursive

  2. 入库模式
     uv run python main.py --store
     uv run python main.py --store --dir Data/docs

  3. 检索模式
     uv run python main.py --query "你的问题"
     uv run python main.py --query "你的问题" --top-k 10

首次运行需先配置 Embedding Provider：
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
    print('配置已保存')
  "
"""

import argparse
import logging
import sys

from rag_service import (
    ConfigurationError,
    get_embeddings_or_raise,
    index_documents,
    load_and_split,
    retrieve,
    validate_embedding,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RAG 文档处理管线 — 加载 → 切割 → 入库 → 检索"
    )

    # 操作模式
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--store",
        action="store_true",
        help="入库模式：加载 → 切割 → 向量化 → 存入 ChromaDB",
    )
    mode.add_argument(
        "--query",
        type=str,
        default=None,
        metavar="TEXT",
        help="检索模式：对 ChromaDB 执行语义搜索并返回结果",
    )

    # 通用参数
    general = parser.add_argument_group("通用参数")
    general.add_argument(
        "--dir",
        default=None,
        help="文档目录路径（默认使用 data_loader 配置的路径）",
    )
    general.add_argument(
        "--splitter",
        default="recursive",
        choices=["recursive", "character"],
        help="文本切割策略（默认 recursive）",
    )
    general.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="检索返回的最相似文档数量（默认 5）",
    )
    general.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="最低相关性分数阈值（0-1，默认不限制）",
    )
    general.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        default=True,
        help="递归扫描文档目录（默认开启）",
    )
    general.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="仅扫描文档目录第一层",
    )
    general.add_argument(
        "--skip-embed",
        action="store_true",
        help="跳过 Embedding 步骤（仅执行加载+切割）",
    )
    general.add_argument(
        "--reindex",
        action="store_true",
        help="强制全量重建（--store 模式下，清空后重新入库所有文档）",
    )
    general.add_argument(
        "--prune-deleted",
        action="store_true",
        help="增量入库时清理本次扫描目录中已删除文件的旧向量",
    )

    args = parser.parse_args()
    if args.top_k <= 0:
        parser.error("--top-k 必须大于 0")
    if args.score_threshold is not None and not 0 <= args.score_threshold <= 1:
        parser.error("--score-threshold 必须在 0 到 1 之间")
    if args.prune_deleted and not args.store:
        parser.error("--prune-deleted 只能与 --store 一起使用")
    return args


def _print_embedding_config_help() -> None:
    logger.error("")
    logger.error("✘ 未配置 Embedding Provider。")
    logger.error("   请先通过以下方式配置：")
    logger.error("")
    logger.error("   uv run python config_demo.py")
    logger.error("")
    logger.error("   或使用 README 中的 save_config 示例。")


def _get_embeddings() -> object:
    """初始化数据库并获取 Embedding 模型。"""
    try:
        return get_embeddings_or_raise()
    except ConfigurationError:
        _print_embedding_config_help()
        sys.exit(1)


def cmd_pipeline(args: argparse.Namespace) -> None:
    """默认模式：加载 → 切割 → 可选验证 Embedding。"""
    print("=" * 55)
    print("  RAG 文档处理管线")
    print("=" * 55)

    # --- Step 1: 加载 ---
    logger.info("")
    logger.info("▶ Step 1/2: 加载并切割文档")
    try:
        pipeline = load_and_split(
            args.dir,
            splitter=args.splitter,
            recursive=args.recursive,
        )
    except (FileNotFoundError, ValueError) as e:
        logger.error("✘ 管线失败: %s", e)
        sys.exit(1)

    # --- Step 3: 可选验证 Embedding ---
    if args.skip_embed:
        logger.info("")
        logger.info("⏭ Step 2/2: 已跳过 Embedding 验证（--skip-embed）")
    else:
        logger.info("")
        logger.info("▶ Step 2/2: 验证 Embedding 模型")
        emb = _get_embeddings()
        logger.info("   Embedding 模型就绪：%s", emb.__class__.__name__)
        try:
            validation = validate_embedding(pipeline.chunks, emb)
            logger.info(
                "   验证：前 %d 个 Chunks 嵌入成功",
                len(validation.vector_dimensions),
            )
            for i, dimension in enumerate(validation.vector_dimensions):
                logger.info("     chunk[%d] → 向量维度: %d", i, dimension)
        except Exception as e:
            logger.error("   嵌入验证失败: %s", e)

    _print_summary(pipeline.documents, pipeline.chunks)


def cmd_store(args: argparse.Namespace) -> None:
    """入库模式：加载 → 切割 → Embedding → 存入 ChromaDB。"""
    print("=" * 55)
    print("  RAG 文档入库")
    print("=" * 55)

    logger.info("")
    logger.info("▶ 执行入库管线")
    try:
        result = index_documents(
            args.dir,
            splitter=args.splitter,
            recursive=args.recursive,
            reindex=args.reindex,
            prune_deleted=args.prune_deleted,
        )
    except (FileNotFoundError, ValueError, ConfigurationError) as e:
        if isinstance(e, ConfigurationError):
            _print_embedding_config_help()
        else:
            logger.error("✘ 入库失败: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("✘ 入库失败: %s", e)
        sys.exit(1)

    logger.info("")
    logger.info("   ✔ 新增/更新: %d Chunks", result.added)
    logger.info("   ✔ 跳过(未变): %d Chunks", result.skipped)
    logger.info("   ✔ 向量库文件数: %d", result.file_count)
    logger.info("   ✔ 向量库总计: %d 个 Chunks", result.total_chunks)
    _print_summary(result.documents, result.chunks)


def cmd_query(args: argparse.Namespace) -> None:
    """检索模式：查询 → Embed → 相似检索 → 展示结果。"""
    print("=" * 55)
    print("  RAG 语义检索")
    print("=" * 55)

    logger.info("")
    logger.info("查询: %s", args.query)

    logger.info("")
    logger.info("▶ ChromaDB 检索 (top-%d)", args.top_k)
    try:
        retrieval = retrieve(
            args.query,
            top_k=args.top_k,
            score_threshold=args.score_threshold,
            include_scores=True,
        )
    except ConfigurationError:
        _print_embedding_config_help()
        sys.exit(1)
    except Exception as e:
        logger.error("✘ 检索失败: %s", e)
        sys.exit(1)

    if retrieval.stats.total_chunks == 0:
        logger.info("   ❌ 向量库为空")
        logger.info("   请先运行 uv run python main.py --store 入库文档")
        return

    if not retrieval.results:
        logger.info("   ❌ 未找到相关结果（向量库可能为空）")
        logger.info("   请先运行 uv run python main.py --store 入库文档")
        return

    logger.info("")
    logger.info("─" * 55)
    logger.info("检索结果（共 %d 条）:", len(retrieval.results))
    logger.info("─" * 55)

    for i, (doc, score) in enumerate(retrieval.scored_results, 1):
        source = doc.metadata.get("source", "未知来源")
        filename = doc.metadata.get("filename", "未知文件")
        content = doc.page_content[:300].replace("\n", " ")
        logger.info("")
        logger.info("  [%d] ─ %s (score: %.4f)", i, filename, score)
        logger.info("      来源: %s", source)
        logger.info("      内容: %s...", content)

    logger.info("")
    logger.info("─" * 55)


def _print_summary(documents, chunks) -> None:
    logger.info("")
    logger.info("-" * 55)
    logger.info("  文档数: %d", len(documents))
    logger.info("  切割后 Chunks: %d", len(chunks))
    logger.info("-" * 55)


def main() -> None:
    args = parse_args()

    if args.query:
        cmd_query(args)
    elif args.store:
        cmd_store(args)
    else:
        cmd_pipeline(args)


if __name__ == "__main__":
    main()
