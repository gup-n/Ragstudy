#!/usr/bin/env python3
"""Chat LLM 配置向导——交互式选择 API 模型或本地模型。"""

import logging
import sys
from getpass import getpass

from embedding import init_db
from llm import get_chat_model, save_config
from llm.config import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    OLLAMA_DEFAULT_BASE_URL,
    OPENAI_COMPATIBLE_DEFAULT_BASE_URL,
)
from llm.schema import LLMConfigCreate

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


PROVIDER_INFO = {
    "openai-compatible": {
        "name": "OpenAI-Compatible",
        "desc": "兼容 OpenAI / DeepSeek / 硅基流动 / OneAPI 等 Chat API",
        "fields": [
            ("model", "模型名称", "gpt-4o-mini"),
            ("base_url", "API 地址", OPENAI_COMPATIBLE_DEFAULT_BASE_URL),
            ("api_key", "API Key", "your_api_key_here"),
        ],
    },
    "ollama": {
        "name": "Ollama",
        "desc": "本地 Ollama Chat 模型",
        "fields": [
            ("model", "模型名称", "qwen2.5:7b"),
            ("base_url", "服务地址", OLLAMA_DEFAULT_BASE_URL),
        ],
    },
}


def print_banner() -> None:
    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║          Chat LLM 配置向导                    ║")
    print("╚═══════════════════════════════════════════════╝")
    print()


def choose_provider() -> str:
    print("可用的 Chat LLM Provider：")
    print()

    providers = list(PROVIDER_INFO.items())
    for i, (_pid, info) in enumerate(providers, 1):
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
    val = input(f"  {prompt} [{default}]: ").strip()
    return val if val else default


def input_float(prompt: str, default: float) -> float:
    while True:
        val = input(f"  {prompt} [{default}]: ").strip()
        if not val:
            return default
        try:
            return float(val)
        except ValueError:
            print("  请输入数字")


def collect_config(provider_id: str) -> LLMConfigCreate:
    info = PROVIDER_INFO[provider_id]
    print()
    print(f"配置 {info['name']} 参数：")
    print()

    kwargs = {"provider": provider_id}
    for field, label, default in info["fields"]:
        if field == "api_key":
            val = getpass(f"  {label} (输入后不可见，可留空): ").strip()
            kwargs[field] = val if val else None
        else:
            kwargs[field] = input_value(label, default)

    kwargs["temperature"] = input_float("生成温度", DEFAULT_TEMPERATURE)
    if provider_id == "openai-compatible":
        kwargs["timeout"] = input_float("请求超时秒数", DEFAULT_TIMEOUT)
    else:
        kwargs["timeout"] = None

    return LLMConfigCreate(**kwargs)


def verify_llm() -> bool:
    print()
    print("▶ 验证 Chat LLM 配置...")

    model = get_chat_model()
    if model is None:
        print("  ✘ 获取 Chat LLM 失败")
        return False

    print(f"  ✔ {model.__class__.__name__} 已创建")
    print("  ℹ 未发送测试请求，避免产生额外 API 调用或本地推理耗时")
    return True


def main() -> None:
    print_banner()

    print("▶ Step 1/4: 初始化数据库...")
    init_db()
    print("  ✔ 就绪")
    print()

    print("▶ Step 2/4: 选择 Provider...")
    provider_id = choose_provider()
    print(f"  已选择: {PROVIDER_INFO[provider_id]['name']}")
    print()

    print("▶ Step 3/4: 填写配置...")
    config = collect_config(provider_id)
    print()

    print("  配置摘要：")
    print(f"    Provider:    {config.provider}")
    print(f"    Model:       {config.model}")
    if config.base_url:
        print(f"    Base URL:    {config.base_url}")
    print(f"    Temperature: {config.temperature}")
    if config.timeout:
        print(f"    Timeout:     {config.timeout}")
    if config.api_key:
        print(f"    API Key:     {'*' * 8} (已加密存储)")
    print()

    confirm = input("  确认保存？(Y/n): ").strip().lower()
    if confirm not in ("", "y", "yes"):
        print("  已取消")
        sys.exit(0)

    print()
    print("▶ Step 4/4: 保存配置...")
    saved = save_config(config)
    print(f"  ✔ 已保存 (id={saved.id})")
    print()

    verify_llm()

    print()
    print("─" * 55)
    print("  配置完成！现在可以：")
    print()
    print("   RAG 问答:  uv run python answer_demo.py")
    print("─" * 55)
    print()


if __name__ == "__main__":
    main()
