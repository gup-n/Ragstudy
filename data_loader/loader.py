"""
文档加载模块 —— RAG 管线的数据入口。

职责：
  原始文档(PDF / TXT / MD / DOCX) →  List[Document]

通过 LOADER_MAPPING 注册表模式，将文件扩展名映射到对应的 Loader 类，
新增格式只需往映射表添加一条记录即可。

运行方式（在项目根目录）：
  uv run python -c "from data_loader import load_documents"
"""

import logging
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.document_loaders import BaseLoader

from data_loader.config import DOCUMENT_DIR, LOADER_MAPPING, LOADER_ARGS

logger = logging.getLogger(__name__)

# 从映射表自动生成受支持的扩展名集合
SUPPORTED_EXTENSIONS = frozenset(LOADER_MAPPING)


def get_loader_for_file(file_path: str) -> Optional[BaseLoader]:
    """根据文件扩展名返回对应的 Loader 实例，不支持的格式返回 None。"""
    # suffix 返回文件扩展名
    ext = Path(file_path).suffix.lower()

    # 获得对应的文档加载器
    loader_cls = LOADER_MAPPING.get(ext)
    if loader_cls is None:
        return None
    # 获得对应的参数
    kwargs = LOADER_ARGS.get(ext, {})

    return loader_cls(file_path, **kwargs)


def load_documents(directory: Optional[str] = None) -> List[Document]:
    """扫描目录下所有支持格式的文档，返回 Document 列表。

    处理流程：
        1. 遍历目录中的文件
        2. 按扩展名筛选支持的文件
        3. 用对应的 Loader 加载内容
        4. 为每个 Document 的 metadata 写入 source 字段
        5. 返回合并后的 Document 列表

    Raises:
        FileNotFoundError: 目录不存在
        ValueError: 没有成功加载任何文档
    """
    dir_path = Path(directory or DOCUMENT_DIR)

    if not dir_path.exists():
        raise FileNotFoundError(f"文档目录不存在: {dir_path}")

    # 所有文档
    all_documents: List[Document] = []
    # 加载的文档
    loaded_files: List[tuple[str, int]] = []
    # 跳过的文档
    skipped_files: List[str] = []
    # 递归时修改:for file_path in sorted(dir_path.rglob("*")):
    for file_path in sorted(dir_path.iterdir()):
        if file_path.is_dir():
            continue
        try:
            loader = get_loader_for_file(str(file_path))
            if loader is None:
                skipped_files.append(file_path.name)
                continue

            docs = loader.load()
            for doc in docs:
                doc.metadata.setdefault("source", str(file_path))
                doc.metadata["filename"] = file_path.name

            all_documents.extend(docs)
            char_count = sum(len(d.page_content) for d in docs)
            loaded_files.append((file_path.name, char_count))

        except Exception as e:
            logger.warning("文件加载失败: %s - %s", file_path.name, e)
            skipped_files.append(file_path.name)

    # 输出摘要
    _print_summary(dir_path, loaded_files, skipped_files, all_documents)

    if not all_documents:
        raise ValueError(
            f"目录 {dir_path} 中没有成功加载任何文档。\n"
            f"请确认：\n"
            f"  1. 目录内包含支持的格式: {', '.join(sorted(SUPPORTED_EXTENSIONS))}\n"
            f"  2. 文件编码为 UTF-8（尤其是 .txt 文件）\n"
            f"  3. PDF 为可提取文本的 PDF；若为扫描件，请确保已配置 OCR。"
        )

    return all_documents


def _print_summary(
    dir_path: Path,
    loaded_files: List[tuple[str, int]],
    skipped_files: List[str],
    documents: List[Document],
) -> None:
    """输出加载结果摘要。"""
    total_chars = sum(len(d.page_content) for d in documents)
    logger.info("文档加载完成: %s", dir_path)
    logger.info("  成功: %d 个文件", len(loaded_files))
    for f in loaded_files:
        logger.info("    ✔ %s ( %d chars )", f[0], f[1])
    if skipped_files:
        logger.info("  跳过: %d 个文件", len(skipped_files))
        for f in skipped_files:
            logger.info("    ✘ %s", f)
    logger.info(
        "总计: %d 个文档片段（来自 %d 个文件）, %s 字符",
        len(documents),
        len(loaded_files),
        f"{total_chars:,}",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        docs = load_documents()
        # print(f"\n共加载 {len(docs)} 个文档片段")
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}")
