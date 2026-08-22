"""
01-HelloLLM.py —— 第 01 章案例：第一次调用大模型

运行方式（必须在项目根目录）：
    python 案例与源码-1-Prompt层/01-HelloLLM.py

演示：
    1. 环境自检（确认能读到 .env）
    2. 同步调用：一次性拿到完整回答
    3. 流式调用：逐字打印
    4. 多轮对话：验证消息历史能累积
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# 让脚本能 import 同目录下的 llm_client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_client import LLMClient


def check_env():
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
    print(f"✅ 环境自检通过：provider={provider}, key_env={key_env}")


def demo_sync(llm: LLMClient):
    """同步调用：等模型把整段回答生成完再返回。"""
    print("\n" + "=" * 50)
    print("① 同步调用")
    print("=" * 50)
    resp = llm.chat([{"role": "user", "content": "用一句话解释什么是 Agent Harness"}])
    print(resp.choices[0].message.content)


def demo_stream(llm: LLMClient):
    """流式调用：边生成边返回。"""
    print("\n" + "=" * 50)
    print("② 流式调用")
    print("=" * 50)
    stream = llm.chat(
        [{"role": "user", "content": "用一句话解释什么是 Agent Harness"}],
        stream=True,
    )
    for chunk in stream:
        # 流式首块的 delta.content 可能为 None，用 or "" 兜底
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
    print()  # 换行


def demo_multi_turn(llm: LLMClient):
    """多轮对话：把历史累积进 messages。下一章会重点讲这个。"""
    print("\n" + "=" * 50)
    print("③ 多轮对话（消息历史累积）")
    print("=" * 50)
    messages = []
    for turn in ["我叫小明", "我叫什么名字？"]:
        print(f"用户：{turn}")
        messages.append({"role": "user", "content": turn})
        resp = llm.chat(messages)
        reply = resp.choices[0].message.content
        print(f"模型：{reply}")
        messages.append({"role": "assistant", "content": reply})


def main():
    check_env()
    llm = LLMClient()
    demo_sync(llm)
    demo_stream(llm)
    demo_multi_turn(llm)


if __name__ == "__main__":
    main()
