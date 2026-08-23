"""01_hello_llm.py —— 第 01 章案例：第一次调用大模型

运行方式（在仓库任意子目录都行）：
    python examples/01_hello_llm.py

演示：
    1. 环境自检（确认能读到 .env）
    2. 同步调用：拿到 LLMResult，取 content
    3. 流式调用：逐块 yield 出文本

注意：多轮对话（消息历史累积）留给第 02 章讲，本章不抢戏。
"""

import os
import sys

# 让脚本能 import 仓库根目录的 harness 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import LLMClient


def check_env() -> str:
    """环境自检：确认 API Key 已配置。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    key_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "ollama": "OLLAMA_API_KEY",
    }
    key_env = key_map[provider]
    key = os.getenv(key_env)
    if not key and provider != "ollama":
        print(f"❌ 未检测到 {key_env}，请先复制 .env-example 为 .env 并填入 API Key")
        print("   cp .env-example .env")
        sys.exit(1)
    return provider


def demo_sync(llm: LLMClient):
    """同步调用：拿 LLMResult，取 content 和 usage。"""
    print("\n" + "=" * 50)
    print("① 同步调用")
    print("=" * 50)
    result = llm.chat([{"role": "user", "content": "用一句话解释什么是 Agent Harness"}])
    print(result.content)
    if result.usage:
        print(f"(token 用量: {result.usage})")


def demo_stream(llm: LLMClient):
    """流式调用：逐块打印文本。"""
    print("\n" + "=" * 50)
    print("② 流式调用")
    print("=" * 50)
    for delta in llm.stream([{"role": "user", "content": "用一句话解释什么是 Agent Harness"}]):
        print(delta, end="", flush=True)
    print()  # 换行


def main():
    provider = check_env()
    print(f"✅ 环境自检通过：provider={provider}")
    llm = LLMClient()
    print(f"   model={llm.model}")
    demo_sync(llm)
    demo_stream(llm)
    print("\n💡 多轮对话与消息历史累积 → 见第 02 章")


if __name__ == "__main__":
    main()
