#!/usr/bin/env python3
"""RAG 问答演示脚本：提问 → 检索 → LLM 生成带引用回答。"""

import argparse
import logging
import sys

from rag_chain import (
    DEFAULT_CONTEXT_MAX_CHARS,
    LLMConfigurationError,
    answer_question,
    create_chat_model,
)
from rag_service import (
    ConfigurationError,
    get_embeddings_or_raise,
    get_vector_store_stats,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def print_banner() -> None:
    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║        RAG 问答演示（检索 + LLM）             ║")
    print("╚═══════════════════════════════════════════════╝")
    print()


def _print_embedding_config_error() -> None:
    print()
    print("✘ 错误：未配置 Embedding Provider。请先运行：")
    print()
    print("   uv run python config_demo.py")
    print()


def _print_llm_config_error(error: Exception) -> None:
    print()
    print(f"✘ 错误：LLM 配置不可用：{error}")
    print()
    print("   请先运行：uv run python llm_config_demo.py")
    print("   也可以复制 .env.example 为 .env，并按需配置 RAG_LLM_* 变量作为部署兜底。")
    print("   不要把真实 API Key 写入 README、history 或提交记录。")
    print()


def _print_answer(result, *, show_context: bool = False) -> None:
    print()
    print("─" * 55)
    print("回答")
    print("─" * 55)
    print(result.answer)
    print()

    if result.sources:
        print("─" * 55)
        print("引用来源")
        print("─" * 55)
        for source in result.sources:
            score = f"{source.score:.4f}" if source.score is not None else "N/A"
            print(
                f"[{source.index}] {source.filename} | "
                f"chunk_id={source.chunk_id} | score={score}"
            )
        print()

    if show_context and result.context:
        print("─" * 55)
        print("上下文")
        print("─" * 55)
        print(result.context)
        print()


def _prepare_runtime():
    try:
        embedding = get_embeddings_or_raise()
    except ConfigurationError:
        _print_embedding_config_error()
        sys.exit(1)

    stats = get_vector_store_stats(embedding)
    if stats.total_chunks == 0:
        print("向量库为空，请先运行：uv run python main.py --store")
        sys.exit(1)

    try:
        llm = create_chat_model()
    except LLMConfigurationError as exc:
        _print_llm_config_error(exc)
        sys.exit(1)

    return embedding, llm, stats


def ask_once(
    query: str,
    *,
    top_k: int,
    score_threshold: float | None,
    context_max_chars: int,
    show_context: bool,
) -> None:
    print_banner()
    embedding, llm, stats = _prepare_runtime()
    print(f"向量库：{stats.total_chunks} 个 Chunks，来自 {len(stats.files)} 个文件")

    try:
        result = answer_question(
            query,
            top_k=top_k,
            score_threshold=score_threshold,
            context_max_chars=context_max_chars,
            embedding=embedding,
            llm=llm,
        )
    except Exception as exc:
        print(f"✘ 问答失败：{exc}")
        sys.exit(1)

    _print_answer(result, show_context=show_context)


def interactive_mode(
    *,
    top_k: int,
    score_threshold: float | None,
    context_max_chars: int,
    show_context: bool,
) -> None:
    print_banner()
    embedding, llm, stats = _prepare_runtime()
    print(f"向量库：{stats.total_chunks} 个 Chunks，来自 {len(stats.files)} 个文件")
    print()
    print("=" * 55)
    print("  交互模式：输入问题开始问答（输入 q 退出）")
    print("=" * 55)
    print()

    while True:
        try:
            query = input("问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not query:
            continue
        if query.lower() in {"q", "quit", "exit"}:
            break

        try:
            result = answer_question(
                query,
                top_k=top_k,
                score_threshold=score_threshold,
                context_max_chars=context_max_chars,
                embedding=embedding,
                llm=llm,
            )
        except Exception as exc:
            print(f"✘ 问答失败：{exc}")
            continue

        _print_answer(result, show_context=show_context)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG 问答演示 — 提问 → 检索 → LLM 生成回答"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="问题文本（留空则进入交互模式）",
    )
    parser.add_argument("--top-k", type=int, default=5, help="检索片段数量")
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="最低相关性分数阈值（0-1，默认不限制）",
    )
    parser.add_argument(
        "--context-max-chars",
        type=int,
        default=DEFAULT_CONTEXT_MAX_CHARS,
        help=f"拼接给 LLM 的上下文最大字符数（默认 {DEFAULT_CONTEXT_MAX_CHARS}）",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="输出实际发送给 LLM 的检索上下文",
    )
    args = parser.parse_args()

    if args.top_k <= 0:
        parser.error("--top-k 必须大于 0")
    if args.score_threshold is not None and not 0 <= args.score_threshold <= 1:
        parser.error("--score-threshold 必须在 0 到 1 之间")
    if args.context_max_chars <= 0:
        parser.error("--context-max-chars 必须大于 0")

    if args.query:
        ask_once(
            args.query,
            top_k=args.top_k,
            score_threshold=args.score_threshold,
            context_max_chars=args.context_max_chars,
            show_context=args.show_context,
        )
    else:
        interactive_mode(
            top_k=args.top_k,
            score_threshold=args.score_threshold,
            context_max_chars=args.context_max_chars,
            show_context=args.show_context,
        )


if __name__ == "__main__":
    main()
