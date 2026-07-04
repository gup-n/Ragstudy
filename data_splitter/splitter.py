"""
文本切割模块 —— RAG 管线的数据预处理阶段。

职责：
    List[Document] -> List[Document]

通过 SPLITTER_MAPPING 注册表模式，将切割策略名称映射到对应的
TextSplitter 类，新增切割策略只需维护映射表即可。

运行方式（在项目根目录）：
    uv run python -c "from text_splitter import split_documents"
"""

import logging
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import TextSplitter

from data_splitter.config import (
    DEFAULT_SPLITTER,
    SPLITTER_MAPPING,
    SPLITTER_ARGS,
)

logger = logging.getLogger(__name__)

SUPPORTED_SPLITTERS = frozenset(SPLITTER_MAPPING)


def get_text_splitter(
    splitter_type: str = DEFAULT_SPLITTER,
) -> TextSplitter:
    """
    根据名称返回对应的 TextSplitter。

    Args:
        splitter_type:
            切割策略名称。

    Returns:
        TextSplitter 实例。

    Raises:
        ValueError:
            不支持的切割策略。
    """
    splitter_cls = SPLITTER_MAPPING.get(splitter_type)

    if splitter_cls is None:
        raise ValueError(
            f"不支持的切割策略: {splitter_type}\n"
            f"支持的策略: {', '.join(sorted(SUPPORTED_SPLITTERS))}"
        )

    # copy() 防止后续修改 kwargs 时影响默认配置
    kwargs = SPLITTER_ARGS.get(splitter_type, {}).copy()

    return splitter_cls(**kwargs)


def split_documents(
    documents: List[Document],
    splitter_type: str = DEFAULT_SPLITTER,
) -> List[Document]:
    """
    将 Document 列表切割为多个文档片段。

    处理流程：
        1. 获取对应 TextSplitter
        2. 执行文本切割
        3. 输出切割摘要
        4. 返回切割后的 Document 列表

    Args:
        documents:
            原始 Document 列表。

        splitter_type:
            切割策略名称。

    Raises:
        ValueError:
            输入文档为空。
    """
    if not documents:
        raise ValueError("没有可切割的文档。")

    splitter = get_text_splitter(splitter_type)

    split_docs = splitter.split_documents(documents)

    _print_summary(
        original_docs=documents,
        split_docs=split_docs,
        splitter_type=splitter_type,
    )

    return split_docs


def _print_summary(
    original_docs: List[Document],
    split_docs: List[Document],
    splitter_type: str,
) -> None:
    """
    输出文本切割摘要。
    """
    original_chars = sum(len(doc.page_content) for doc in original_docs)
    split_chars = sum(len(doc.page_content) for doc in split_docs)

    avg_chunk_chars = split_chars / len(split_docs) if split_docs else 0

    logger.info("文本切割完成")
    logger.info("  切割策略: %s", splitter_type)
    logger.info("  原始文档: %d", len(original_docs))
    logger.info("  切割后片段: %d", len(split_docs))
    logger.info("  原始字符数: %s", f"{original_chars:,}")
    logger.info("  切割后字符数: %s", f"{split_chars:,}")
    logger.info("  平均 Chunk 长度: %.1f chars", avg_chunk_chars)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    from data_loader import load_documents

    try:
        docs = load_documents()
        chunks = split_documents(docs)

        print(f"\n共生成 {len(chunks)} 个文档片段")

    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}")
