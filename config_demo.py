#!/usr/bin/env python3
"""Embedding 配置向导——交互式选择 Provider 并保存配置。

用法：
  uv run python config_demo.py

支持的 Provider：
  1. OpenAI-Compatible  — OpenAI / DeepSeek / 硅基流动 / OneAPI 等
  2. Ollama             — 本地 Ollama 服务
  3. HuggingFace        — 本地 HuggingFace 模型
"""

import logging
import sys
from getpass import getpass

from embedding import init_db, save_config, get_embedding
from embedding.schema import EmbeddingConfigCreate

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


PROVIDER_INFO = {
    "openai-compatible": {
        "name": "OpenAI-Compatible",
        "desc": "兼容 OpenAI / DeepSeek / 硅基流动 / OneAPI 等",
        "fields": [
            ("model", "模型名称", "text-embedding-3-small"),
            ("base_url", "API 地址", "https://api.openai.com/v1"),
            ("api_key", "API Key", "sk-..."),
        ],
    },
    "ollama": {
        "name": "Ollama",
        "desc": "本地 Ollama 服务的 Embedding 端点",
        "fields": [
            ("model", "模型名称", "nomic-embed-text"),
            ("base_url", "服务地址", "http://localhost:11434"),
        ],
    },
    "huggingface": {
        "name": "HuggingFace",
        "desc": "本地 HuggingFace 模型",
        "fields": [
            ("model", "模型名称", "BAAI/bge-small-zh-v1.5"),
        ],
    },
}


def print_banner():
    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║        Embedding Provider 配置向导            ║")
    print("╚═══════════════════════════════════════════════╝")
    print()


def choose_provider() -> str:
    """让用户选择 Provider，返回 provider id。"""
    print("可用的 Embedding Provider：")
    print()

    providers = list(PROVIDER_INFO.items())
    for i, (pid, info) in enumerate(providers, 1):
        print(f"  [{i}] {info['name']}")
        print(f"      {info['desc']}")
        print()

    while True:
        try:
            choice = input(f"请选择 (1-{len(providers)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                return providers[idx][0]
        except (ValueError, IndexError):
            pass
        print(f"  无效输入，请输入 1-{len(providers)}")


def input_value(prompt: str, default: str) -> str:
    """带默认值的输入。"""
    val = input(f"  {prompt} [{default}]: ").strip()
    return val if val else default


def collect_config(provider_id: str) -> EmbeddingConfigCreate:
    """交互式收集配置参数。"""
    info = PROVIDER_INFO[provider_id]
    print()
    print(f"配置 {info['name']} 参数：")
    print()

    kwargs = {"provider": provider_id}

    for field, label, default in info["fields"]:
        if field == "api_key":
            val = getpass(f"  {label} (输入后不可见): ").strip()
            kwargs[field] = val if val else None
        else:
            kwargs[field] = input_value(label, default)

    # 处理 extra 字段（HuggingFace 需要设备参数）
    extra = None
    if provider_id == "huggingface":
        device = input_value("运行设备", "cpu")
        extra = {"device": device}
    kwargs["extra"] = extra

    return EmbeddingConfigCreate(**kwargs)


def verify_embedding():
    """验证配置是否可用。"""
    print()
    print("▶ 验证 Embedding 模型...")

    emb = get_embedding()
    if emb is None:
        print("  ✘ 获取 Embedding 模型失败")
        return False

    try:
        test_texts = ["Hello, world!", "RAG 文档检索"]
        vectors = emb.embed_documents(test_texts)
        for i, vec in enumerate(vectors):
            print(f"  ✔ 测试文本 [{i}] → 向量维度: {len(vec)}")
        print()
        print("  ✅ 配置验证通过！")
        return True
    except Exception as e:
        print(f"  ✘ 验证失败: {e}")
        return False


def main():
    print_banner()

    # Step 1: 初始化数据库
    print("▶ Step 1/4: 初始化数据库...")
    init_db()
    print("  ✔ 就绪")
    print()

    # Step 2: 选择 Provider
    print("▶ Step 2/4: 选择 Provider...")
    provider_id = choose_provider()
    print(f"  已选择: {PROVIDER_INFO[provider_id]['name']}")
    print()

    # Step 3: 填写配置
    print("▶ Step 3/4: 填写配置...")
    config = collect_config(provider_id)
    print()

    # 确认
    print("  配置摘要：")
    print(f"    Provider: {config.provider}")
    print(f"    Model:    {config.model}")
    if config.base_url:
        print(f"    Base URL: {config.base_url}")
    if config.api_key:
        print(f"    API Key:  {'*' * 8} (已加密存储)")
    print()

    confirm = input("  确认保存？(Y/n): ").strip().lower()
    if confirm not in ("", "y", "yes"):
        print("  已取消")
        sys.exit(0)

    # Step 4: 保存
    print()
    print("▶ Step 4/4: 保存配置...")
    saved = save_config(config)
    print(f"  ✔ 已保存 (id={saved.id})")
    print()

    # 验证
    verify_embedding()

    print()
    print("─" * 55)
    print("  配置完成！现在可以：")
    print()
    print("   入库文档:  uv run python main.py --store")
    print("   查询演示:  uv run python query_demo.py")
    print("─" * 55)
    print()


if __name__ == "__main__":
    main()
