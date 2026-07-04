"""无需 pytest 的轻量逻辑检查。

用途是在测试工具尚未安装时，快速验证核心纯逻辑仍然可用。
正式开发仍建议运行 `pytest tests`。
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from langchain_core.documents import Document
from pydantic import ValidationError

from data_loader.loader import load_documents
from data_splitter.splitter import split_documents
from embedding.schema import EmbeddingConfigCreate
from vector_store.store import (
    _ensure_chunk_ids,
    _fingerprint_matches,
    _group_by_source_id,
)


def check_data_loader() -> None:
    with TemporaryDirectory() as tmp:
        docs_dir = Path(tmp) / "docs"
        nested_dir = docs_dir / "nested"
        nested_dir.mkdir(parents=True)
        (docs_dir / "root.txt").write_text("根目录文档", encoding="utf-8")
        (nested_dir / "child.md").write_text("# 子目录文档", encoding="utf-8")

        docs = load_documents(str(docs_dir))
        source_ids = {doc.metadata["source_id"] for doc in docs}
        assert source_ids == {"root.txt", "nested/child.md"}

        first_level_docs = load_documents(str(docs_dir), recursive=False)
        assert [doc.metadata["source_id"] for doc in first_level_docs] == ["root.txt"]


def check_splitter() -> None:
    text = "第一段内容。" * 200
    docs = [
        Document(
            page_content=text,
            metadata={"source_id": "guide.md", "filename": "guide.md"},
        )
    ]
    chunks = split_documents(docs)
    assert chunks
    for index, chunk in enumerate(chunks):
        assert chunk.metadata["chunk_index"] == index
        assert chunk.metadata["chunk_id"] == f"guide.md::chunk-{index}"


def check_vector_metadata() -> None:
    chunks = [
        Document(page_content="a", metadata={"source_id": "docs/a.txt"}),
        Document(page_content="b", metadata={"source_id": "docs/a.txt"}),
    ]
    ids = _ensure_chunk_ids(chunks)
    assert ids == ["docs/a.txt::chunk-0", "docs/a.txt::chunk-1"]

    grouped = _group_by_source_id(
        [
            Document(page_content="a", metadata={"source_id": "a/readme.md"}),
            Document(page_content="b", metadata={"source_id": "b/readme.md"}),
        ]
    )
    assert set(grouped) == {"a/readme.md", "b/readme.md"}

    stored = {"content_hash": "old", "mtime": 1.0, "size": 100}
    current = {"content_hash": "new", "file_mtime": 1.0, "file_size": 100}
    assert not _fingerprint_matches(stored, current)


def check_embedding_schema() -> None:
    try:
        EmbeddingConfigCreate(provider="huggingface", model=" ")
    except ValidationError:
        pass
    else:
        raise AssertionError("empty model should be rejected")

    config = EmbeddingConfigCreate(
        provider="openai-compatible",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        api_key=" sk-test ",
    )
    assert config.api_key == "sk-test"


def main() -> None:
    check_data_loader()
    check_splitter()
    check_vector_metadata()
    check_embedding_schema()
    print("manual logic checks passed")


if __name__ == "__main__":
    main()
