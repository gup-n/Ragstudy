"""RAG answer chain: retrieve context, call a chat model, return cited answers."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage, SystemMessage

from llm import LLMConfig, LLMConfigurationError, get_chat_model
from llm.factory import create_chat_model as create_chat_model_from_config
from rag_service import RetrievalResult, retrieve

DEFAULT_CONTEXT_MAX_CHARS = 12000


@dataclass(frozen=True)
class SourceReference:
    index: int
    filename: str
    source_id: str
    chunk_id: str
    score: float | None
    excerpt: str


@dataclass(frozen=True)
class RagAnswer:
    question: str
    answer: str
    sources: list[SourceReference]
    context: str
    retrieval: RetrievalResult


def create_chat_model(config: LLMConfig | None = None) -> Any:
    """Create a chat model from explicit config or the enabled LLM config."""
    if config is not None:
        return create_chat_model_from_config(config)

    chat_model = get_chat_model()
    if chat_model is None:
        raise LLMConfigurationError(
            "未配置 Chat LLM。请先运行 `uv run python llm_config_demo.py`，"
            "或使用 RAG_LLM_* 环境变量作为部署兜底。"
        )
    return chat_model


def _metadata_value(doc: Document, key: str, default: str = "未知") -> str:
    value = doc.metadata.get(key)
    return str(value) if value not in (None, "") else default


def _normalize_content(content: str) -> str:
    return "\n".join(line.rstrip() for line in content.strip().splitlines()).strip()


def build_context(
    scored_results: list[tuple[Document, float | None]],
    *,
    max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
) -> tuple[str, list[SourceReference]]:
    """Build a compact cited context block from retrieved chunks."""
    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")

    blocks: list[str] = []
    sources: list[SourceReference] = []
    used_chars = 0

    for doc, score in scored_results:
        content = _normalize_content(doc.page_content)
        if not content:
            continue

        index = len(sources) + 1
        filename = _metadata_value(doc, "filename")
        source_id = _metadata_value(
            doc,
            "source_id",
            _metadata_value(doc, "relative_path", filename),
        )
        chunk_id = _metadata_value(
            doc,
            "chunk_id",
            f"{source_id}::chunk-{doc.metadata.get('chunk_index', '?')}",
        )
        score_text = f"{score:.4f}" if score is not None else "N/A"
        header = (
            f"[{index}]\n"
            f"文件: {filename}\n"
            f"source_id: {source_id}\n"
            f"chunk_id: {chunk_id}\n"
            f"score: {score_text}\n"
            "内容:\n"
        )
        separator = "\n\n"
        remaining = max_chars - used_chars - len(header) - len(separator)
        if remaining <= 0:
            break

        if len(content) > remaining:
            suffix = "..."
            excerpt = content[: max(0, remaining - len(suffix))].rstrip()
            excerpt = (excerpt.rstrip(".。 ") + suffix)[:remaining]
        else:
            excerpt = content[:remaining].rstrip()

        block = f"{header}{excerpt}"
        blocks.append(block)
        used_chars += len(block) + len(separator)
        sources.append(
            SourceReference(
                index=index,
                filename=filename,
                source_id=source_id,
                chunk_id=chunk_id,
                score=score,
                excerpt=excerpt,
            )
        )

    return "\n\n".join(blocks), sources


def build_messages(question: str, context: str) -> list[SystemMessage | HumanMessage]:
    """Create the chat prompt used by the RAG answer chain."""
    system_prompt = (
        "你是一个严谨的 RAG 问答助手。只能根据给定上下文回答。"
        "如果上下文不足以回答问题，直接说明无法从现有资料确认。"
        "回答应简洁、准确，并在关键结论后使用 [1]、[2] 这样的来源编号。"
    )
    user_prompt = (
        f"问题：{question}\n\n"
        "检索上下文：\n"
        f"{context}\n\n"
        "请基于以上上下文回答，并列出必要的来源编号。"
    )
    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def _response_to_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content).strip()


def _empty_answer(
    question: str,
    message: str,
    retrieval: RetrievalResult,
) -> RagAnswer:
    return RagAnswer(
        question=question,
        answer=message,
        sources=[],
        context="",
        retrieval=retrieval,
    )


def answer_question(
    question: str,
    *,
    top_k: int = 5,
    score_threshold: float | None = None,
    context_max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
    embedding: Embeddings | None = None,
    llm: Any | None = None,
) -> RagAnswer:
    """Run retrieval and generate a cited answer with a chat LLM."""
    question = question.strip()
    if not question:
        raise ValueError("question 不能为空")

    retrieval = retrieve(
        question,
        top_k=top_k,
        score_threshold=score_threshold,
        include_scores=True,
        embedding=embedding,
    )
    if retrieval.stats.total_chunks == 0:
        return _empty_answer(
            question,
            "向量库为空，无法回答。请先运行 `uv run python main.py --store` 入库文档。",
            retrieval,
        )

    context, sources = build_context(
        retrieval.scored_results,
        max_chars=context_max_chars,
    )
    if not sources:
        return _empty_answer(
            question,
            "未检索到足够相关的资料，无法从现有知识库确认答案。",
            retrieval,
        )

    chat_model = llm or create_chat_model()
    response = chat_model.invoke(build_messages(question, context))
    return RagAnswer(
        question=question,
        answer=_response_to_text(response),
        sources=sources,
        context=context,
        retrieval=retrieval,
    )
