#!/usr/bin/env python3
"""RAG 查询演示脚本——提问 → 检索 → 展示结果（无需 LLM）。

展示向量检索的效果：输入一个问题，从 ChromaDB 中找到最相关的文档片段。

用法：
  uv run python query_demo.py
  uv run python query_demo.py "RAG 的工作原理"
  uv run python query_demo.py --query "向量化" --top-k 10
"""

import argparse
import logging
import sys

from embedding import get_embedding, init_db
from vector_store import get_file_list, search, count_documents

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def print_banner() -> None:
    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║        RAG 语义检索演示（无需 LLM）           ║")
    print("╚═══════════════════════════════════════════════╝")
    print()


def print_result(index: int, doc, score: float | None = None) -> None:
    """格式化打印一条检索结果。"""
    filename = doc.metadata.get("filename", "?")
    source = doc.metadata.get("source", "?")
    content = doc.page_content.strip()

    print(f"  ── 结果 #{index} {'(score: %.4f)' % score if score is not None else ''}──")
    print(f"     文件: {filename}")
    print(f"     路径: {source}")
    print("     内容:")
    for line in content.split("\n"):
        print(f"       {line}")
    print()


def demo(query: str, top_k: int = 5) -> None:
    """执行一次检索并展示结果。"""
    print_banner()

    # Step 1: Embedding 模型
    print("▶ Step 1/3: 初始化 Embedding 模型...")
    init_db()
    emb = get_embedding()
    if emb is None:
        print()
        print("✘ 错误：未配置 Embedding Provider。请先运行：")
        print()
        print("   uv run python -c \"\"\"")
        print("   from embedding import init_db, save_config")
        print("   from embedding.schema import EmbeddingConfigCreate")
        print("   init_db()")
        print("   cfg = EmbeddingConfigCreate(provider='openai-compatible', ...)")
        print("   save_config(cfg)")
        print('   """')
        sys.exit(1)
    print(f"   ✔ {emb.__class__.__name__} 就绪")
    print()

    # Step 2: 向量库状态
    print("▶ Step 2/3: 检查向量库状态...")
    total = count_documents(emb)
    files = get_file_list(emb)
    print(f"   ✔ 向量库共 {total} 个 Chunks，来自 {len(files)} 个文件")
    if files:
        for f in files:
            print(f"      · {f}")
    print()

    if total == 0:
        print("⚠ 向量库为空！请先入库文档：")
        print()
        print("   uv run python main.py --store")
        print()
        sys.exit(1)

    # Step 3: 检索
    print(f"▶ Step 3/3: 语义检索「{query}」(top-{top_k})...")
    print()

    results = search(query, emb, k=top_k)

    if not results:
        print("  ❌ 未找到相关结果")
        print()
        return

    print(f"   ✔ 找到 {len(results)} 个相关片段")
    print()
    print("─" * 55)
    print("  检索结果")
    print("─" * 55)
    print()

    for i, doc in enumerate(results, 1):
        print_result(i, doc)

    print("─" * 55)
    print("  提示：将检索结果与大语言模型结合，即可实现完整 RAG 问答。")
    print("─" * 55)
    print()


def interactive_mode(top_k: int = 5) -> None:
    """交互式检索：反复输入问题，Ctrl+C 退出。"""
    # 预先初始化
    print_banner()
    print("▶ 初始化 Embedding 模型和向量库...")
    init_db()
    emb = get_embedding()
    if emb is None:
        print("✘ 未配置 Embedding Provider")
        sys.exit(1)

    total = count_documents(emb)
    files = get_file_list(emb)
    print(f"   ✔ 向量库共 {total} 个 Chunks，来自 {len(files)} 个文件")
    if total == 0:
        print("⚠ 向量库为空！请先运行 uv run python main.py --store")
        sys.exit(1)

    print()
    print("=" * 55)
    print("  交互模式：输入问题开始检索（输入 q 退出）")
    print("=" * 55)
    print()

    while True:
        try:
            query = input("❓ 问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("👋 再见！")
            break

        if not query:
            continue
        if query.lower() in ("q", "quit", "exit"):
            print("👋 再见！")
            break

        print()
        results = search(query, emb, k=top_k)
        print()

        if not results:
            print("  ❌ 未找到相关结果")
            print()
            continue

        for i, doc in enumerate(results, 1):
            print_result(i, doc)

        print("─" * 55)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG 查询演示 — 提问 → 检索 → 展示结果（无需 LLM）"
    )
    parser.add_argument(
        "query",
        nargs="?",
        type=str,
        default=None,
        help="查询文本（留空则进入交互模式）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="检索返回的最相似文档数量（默认 5）",
    )
    args = parser.parse_args()

    if args.query:
        demo(args.query, top_k=args.top_k)
    else:
        interactive_mode(top_k=args.top_k)


if __name__ == "__main__":
    main()
