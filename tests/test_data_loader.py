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
