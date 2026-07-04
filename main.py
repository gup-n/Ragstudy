"""RAG 文档处理管线 — 端到端入口。

完整流程：
  1. 加载 — data_loader.load_documents()    原始文档 → List[Document]
  2. 切割 — data_splitter.split_documents()  List[Document] → 更小的 Chunks
  3. 向量化 — embedding.get_embedding()      文本 → 向量（需先配置 Provider）

用法：
  uv run python main.py
  uv run python main.py --dir Data/docs --splitter recursive

首次运行需先配置 Embedding Provider（否则步骤 3 会提示）：
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
from embedding import init_db, get_embedding

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RAG 文档处理管线 — 加载 → 切割 → 向量化"
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="文档目录路径（默认使用 data_loader 配置的路径）",
    )
    parser.add_argument(
        "--splitter",
        default="recursive",
        choices=["recursive", "character"],
        help="文本切割策略（默认 recursive）",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="跳过向量化步骤（仅执行加载+切割）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ------------------------------------------------------------------
    # 步骤 1：加载文档
    # ------------------------------------------------------------------
    print("=" * 55)
    print("  RAG 文档处理管线")
    print("=" * 55)

    logger.info("")
    logger.info("▶ Step 1/3: 加载文档")

    try:
        documents = load_documents(args.dir)
    except (FileNotFoundError, ValueError) as e:
        logger.error("✘ 加载失败: %s", e)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 步骤 2：切割文本
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("▶ Step 2/3: 切割文本")

    try:
        chunks = split_documents(documents, args.splitter)
    except ValueError as e:
        logger.error("✘ 切割失败: %s", e)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 步骤 3：向量化（可选）
    # ------------------------------------------------------------------
    if args.skip_embed:
        logger.info("")
        logger.info("⏭ Step 3/3: 已跳过（--skip-embed）")
    else:
        logger.info("")
        logger.info("▶ Step 3/3: 初始化 Embedding 模型")

        # 初始化数据库（首次运行会创建表）
        init_db()

        emb = get_embedding()
        if emb is None:
            logger.info("")
            logger.info("⚠  未配置 Embedding Provider。")
            logger.info("   请先通过以下方式配置：")
            logger.info("")
            logger.info("   uv run python -c \"\"\"")
            logger.info("   from embedding import init_db, save_config")
            logger.info("   from embedding.schema import EmbeddingConfigCreate")
            logger.info("")
            logger.info("   init_db()")
            logger.info('   cfg = EmbeddingConfigCreate(')
            logger.info("       provider='openai-compatible',")
            logger.info("       model='text-embedding-3-small',")
            logger.info("       base_url='https://api.openai.com/v1',")
            logger.info("       api_key='sk-...',")
            logger.info("   )")
            logger.info("   save_config(cfg)")
            logger.info("   print('配置已保存')")
            logger.info("   \"\"\"")
        else:
            # 取前 3 个 chunks 试嵌入，展示效果
            sample_texts = [c.page_content[:200] for c in chunks[:3]]
            logger.info("   Embedding 模型就绪：%s", emb.__class__.__name__)
            try:
                vectors = emb.embed_documents(sample_texts)
                logger.info("   验证：对前 3 个片段执行嵌入成功")
                for i, vec in enumerate(vectors):
                    logger.info("     chunk[%d] → 向量维度: %d", i, len(vec))
            except Exception as e:
                logger.error("   嵌入验证失败: %s", e)

    # ------------------------------------------------------------------
    # 最终摘要
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("-" * 55)
    logger.info("管线执行完毕")
    logger.info("  文档数: %d", len(documents))
    logger.info("  切割后 Chunks: %d", len(chunks))
    logger.info("-" * 55)


if __name__ == "__main__":
    main()
