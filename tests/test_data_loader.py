import pytest

from data_loader.loader import load_documents


def test_load_documents_recurses_and_sets_source_metadata(tmp_path):
    docs_dir = tmp_path / "docs"
    nested_dir = docs_dir / "nested"
    nested_dir.mkdir(parents=True)
    (docs_dir / "root.txt").write_text("根目录文档", encoding="utf-8")
    (nested_dir / "child.md").write_text("# 子目录文档", encoding="utf-8")

    docs = load_documents(str(docs_dir))

    source_ids = {doc.metadata["source_id"] for doc in docs}
    assert source_ids == {"root.txt", "nested/child.md"}
    assert all(doc.metadata["doc_root"] == str(docs_dir.resolve()) for doc in docs)
    assert all(doc.metadata["source"] for doc in docs)


def test_load_documents_can_scan_first_level_only(tmp_path):
    docs_dir = tmp_path / "docs"
    nested_dir = docs_dir / "nested"
    nested_dir.mkdir(parents=True)
    (docs_dir / "root.txt").write_text("根目录文档", encoding="utf-8")
    (nested_dir / "child.md").write_text("# 子目录文档", encoding="utf-8")

    docs = load_documents(str(docs_dir), recursive=False)

    assert [doc.metadata["source_id"] for doc in docs] == ["root.txt"]


def test_load_documents_skips_empty_files(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "empty.txt").write_text("", encoding="utf-8")
    (docs_dir / "valid.txt").write_text("有效内容", encoding="utf-8")

    docs = load_documents(str(docs_dir))

    assert [doc.metadata["source_id"] for doc in docs] == ["valid.txt"]


def test_load_documents_raises_when_only_empty_files(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "empty.txt").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="没有成功加载任何文档"):
        load_documents(str(docs_dir))


def test_load_documents_strict_raises_on_load_failure(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "valid.txt").write_text("有效内容", encoding="utf-8")
    (docs_dir / "bad.txt").write_bytes(b"\xff\xfe\x00")

    docs = load_documents(str(docs_dir))
    assert [doc.metadata["source_id"] for doc in docs] == ["valid.txt"]

    with pytest.raises(ValueError, match="有文件加载失败"):
        load_documents(str(docs_dir), strict=True)
