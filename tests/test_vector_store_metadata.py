from langchain_core.documents import Document

from vector_store.store import (
    _ensure_chunk_ids,
    _fingerprint_matches,
    _group_by_source_id,
)


def test_ensure_chunk_ids_uses_source_id_and_chunk_index():
    chunks = [
        Document(page_content="a", metadata={"source_id": "docs/a.txt"}),
        Document(page_content="b", metadata={"source_id": "docs/a.txt"}),
    ]

    ids = _ensure_chunk_ids(chunks)

    assert ids == ["docs/a.txt::chunk-0", "docs/a.txt::chunk-1"]
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[1].metadata["chunk_index"] == 1


def test_group_by_source_id_keeps_same_filenames_separate():
    chunks = [
        Document(
            page_content="a",
            metadata={"source_id": "dept-a/readme.md", "filename": "readme.md"},
        ),
        Document(
            page_content="b",
            metadata={"source_id": "dept-b/readme.md", "filename": "readme.md"},
        ),
    ]

    groups = _group_by_source_id(chunks)

    assert set(groups) == {"dept-a/readme.md", "dept-b/readme.md"}


def test_fingerprint_prefers_content_hash():
    stored = {"content_hash": "old", "mtime": 1.0, "size": 100}
    current = {"content_hash": "new", "file_mtime": 1.0, "file_size": 100}

    assert not _fingerprint_matches(stored, current)
