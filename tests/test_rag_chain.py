from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from rag_chain import (
    SourceReference,
    _response_to_text,
    build_context,
    build_messages,
)


def test_build_context_adds_cited_source_metadata():
    doc = Document(
        page_content="奖学金申请需要提交申请表和相关证明材料。",
        metadata={
            "filename": "scholarship.txt",
            "source_id": "policy/scholarship.txt",
            "chunk_id": "policy/scholarship.txt::chunk-0",
        },
    )

    context, sources = build_context([(doc, 0.91)])

    assert "[1]" in context
    assert "policy/scholarship.txt::chunk-0" in context
    assert sources == [
        SourceReference(
            index=1,
            filename="scholarship.txt",
            source_id="policy/scholarship.txt",
            chunk_id="policy/scholarship.txt::chunk-0",
            score=0.91,
            excerpt="奖学金申请需要提交申请表和相关证明材料。",
        )
    ]


def test_build_context_respects_max_chars():
    doc = Document(
        page_content="长内容" * 100,
        metadata={"filename": "long.txt", "source_id": "long.txt"},
    )

    context, sources = build_context([(doc, None)], max_chars=120)

    assert len(context) <= 120
    assert sources
    assert sources[0].excerpt.endswith("...")


def test_build_messages_instructs_model_to_use_citations():
    messages = build_messages("如何申请？", "[1]\n内容:\n按流程申请。")

    assert len(messages) == 2
    assert "只能根据给定上下文回答" in messages[0].content
    assert "[1]" in messages[1].content


def test_response_to_text_handles_chat_message():
    assert _response_to_text(AIMessage(content=" 回答内容 ")) == "回答内容"
