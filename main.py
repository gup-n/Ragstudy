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

from data_loader import load_documents
from data_splitter import split_documents
from embedding import get_embedding, init_db
from vector_store import add_to_store, search, count_documents, force_reindex, get_file_list

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
    mode = parser.add_argument_group("操作模式（三选一，默认仅执行加载+切割+验证）")
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
        "--skip-embed",
        action="store_true",
        help="跳过 Embedding 步骤（仅执行加载+切割）",
    )
    general.add_argument(
        "--reindex",
        action="store_true",
        help="强制全量重建（--store 模式下，清空后重新入库所有文档）",
    )

    return parser.parse_args()


def _get_embeddings() -> any:
    """初始化数据库并获取 Embedding 模型。"""
    init_db()
    emb = get_embedding()
    if emb is None:
        logger.error("")
        logger.error("✘ 未配置 Embedding Provider。")
        logger.error("   请先通过以下方式配置：")
        logger.error("")
        logger.error("   uv run python -c \"\"\"")
        logger.error("   from embedding import init_db, save_config")
        logger.error("   from embedding.schema import EmbeddingConfigCreate")
        logger.error("")
        logger.error("   init_db()")
        logger.error("   cfg = EmbeddingConfigCreate(provider='openai-compatible', ...)")
        logger.error("   save_config(cfg)")
        logger.error("   \"\"\"")
        sys.exit(1)
    return emb


def cmd_pipeline(args: argparse.Namespace) -> None:
    """默认模式：加载 → 切割 → 可选验证 Embedding。"""
    print("=" * 55)
    print("  RAG 文档处理管线")
    print("=" * 55)

    # --- Step 1: 加载 ---
    logger.info("")
    logger.info("▶ Step 1/3: 加载文档")
    try:
        documents = load_documents(args.dir)
    except (FileNotFoundError, ValueError) as e:
        logger.error("✘ 加载失败: %s", e)
        sys.exit(1)

    # --- Step 2: 切割 ---
    logger.info("")
    logger.info("▶ Step 2/3: 切割文本")
    try:
        chunks = split_documents(documents, args.splitter)
    except ValueError as e:
        logger.error("✘ 切割失败: %s", e)
        sys.exit(1)

    # --- Step 3: 可选验证 Embedding ---
    if args.skip_embed:
        logger.info("")
        logger.info("⏭ Step 3/3: 已跳过（--skip-embed）")
    else:
        logger.info("")
        logger.info("▶ Step 3/3: 验证 Embedding 模型")
        emb = _get_embeddings()
        sample_texts = [c.page_content[:200] for c in chunks[:3]]
        logger.info("   Embedding 模型就绪：%s", emb.__class__.__name__)
        try:
            vectors = emb.embed_documents(sample_texts)
            logger.info("   验证：前 %d 个 Chunks 嵌入成功", len(vectors))
            for i, vec in enumerate(vectors):
                logger.info("     chunk[%d] → 向量维度: %d", i, len(vec))
        except Exception as e:
            logger.error("   嵌入验证失败: %s", e)

    _print_summary(documents, chunks)


def cmd_store(args: argparse.Namespace) -> None:
    """入库模式：加载 → 切割 → Embedding → 存入 ChromaDB。"""
    print("=" * 55)
    print("  RAG 文档入库")
    print("=" * 55)

    # --- Step 1: 加载 ---
    logger.info("")
    logger.info("▶ Step 1/4: 加载文档")
    try:
        documents = load_documents(args.dir)
    except (FileNotFoundError, ValueError) as e:
        logger.error("✘ 加载失败: %s", e)
        sys.exit(1)

    # --- Step 2: 切割 ---
    logger.info("")
    logger.info("▶ Step 2/4: 切割文本")
    try:
        chunks = split_documents(documents, args.splitter)
    except ValueError as e:
        logger.error("✘ 切割失败: %s", e)
        sys.exit(1)

    # --- Step 3: Embedding 模型 ---
    logger.info("")
    logger.info("▶ Step 3/4: 初始化 Embedding 模型")
    emb = _get_embeddings()
    logger.info("   ✔ %s 就绪", emb.__class__.__name__)

    # --- Step 4: 入库 ---
    logger.info("")
    if args.reindex:
        logger.info("▶ Step 4/4: 全量重建索引（--reindex）")
        try:
            n = force_reindex(chunks, emb)
            total = count_documents(emb)
            logger.info("   ✔ 全量重建完成: %d 个 Chunks", n)
            logger.info("   ✔ 向量库总计: %d 个 Chunks", total)
        except Exception as e:
            logger.error("✘ 重建失败: %s", e)
            sys.exit(1)
    else:
        logger.info("▶ Step 4/4: 增量入库 ChromaDB")
        file_count = len(get_file_list(emb))
        logger.info("   向量库已有 %d 个文件", file_count)
        try:
            added, skipped = add_to_store(chunks, emb)
            total = count_documents(emb)
            logger.info("   ✔ 新增/更新: %d Chunks", added)
            logger.info("   ✔ 跳过(未变): %d Chunks", skipped)
            logger.info("   ✔ 向量库总计: %d 个 Chunks", total)
        except Exception as e:
            logger.error("✘ 入库失败: %s", e)
            sys.exit(1)

    _print_summary(documents, chunks)


def cmd_query(args: argparse.Namespace) -> None:
    """检索模式：查询 → Embed → 相似检索 → 展示结果。"""
    print("=" * 55)
    print("  RAG 语义检索")
    print("=" * 55)

    logger.info("")
    logger.info("查询: %s", args.query)

    # --- Embedding 模型 ---
    logger.info("")
    logger.info("▶ Step 1/2: 初始化 Embedding 模型")
    emb = _get_embeddings()

    # --- 检索 ---
    logger.info("")
    logger.info("▶ Step 2/2: ChromaDB 检索 (top-%d)", args.top_k)
    try:
        results = search(args.query, emb, k=args.top_k)
    except Exception as e:
        logger.error("✘ 检索失败: %s", e)
        sys.exit(1)

    if not results:
        logger.info("   ❌ 未找到相关结果（向量库可能为空）")
        logger.info("   请先运行 uv run python main.py --store 入库文档")
        return

    logger.info("")
    logger.info("─" * 55)
    logger.info("检索结果（共 %d 条）:", len(results))
    logger.info("─" * 55)

    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("source", "未知来源")
        filename = doc.metadata.get("filename", "未知文件")
        content = doc.page_content[:300].replace("\n", " ")
        logger.info("")
        logger.info("  [%d] ─ %s", i, filename)
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
