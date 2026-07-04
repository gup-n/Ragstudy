from langchain_core.documents import Document

from data_splitter.splitter import split_documents


def test_split_documents_adds_stable_chunk_metadata():
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
