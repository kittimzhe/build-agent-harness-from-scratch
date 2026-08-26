"""02_chat_history.py —— 第 02 章案例：消息状态与上下文窗口

运行方式（在仓库任意子目录都行）：
    python examples/02_chat_history.py

演示：
    1. 多轮对话：消息历史怎么让模型「记得」上文
    2. Token 与成本：每轮用量、累积用量，观察多轮对话成本怎么涨
    3. 历史治理第一刀：截断（truncate）前后对比，模型会「忘事」
"""

import os
import sys

from dotenv import load_dotenv, find_dotenv

# 找到仓库根目录的 .env（案例可在任意子目录运行）
load_dotenv(find_dotenv(usecwd=True))

# 让脚本能 import 仓库根目录的 harness 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import ChatSession, LLMClient
from harness.llm import PROVIDERS


def check_env() -> str:
    """环境自检：确认 API Key 已配置（提供商表直接读内核的 PROVIDERS，不重复维护）。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未检测到 {key_env}，请先复制 .env-example 为 .env 并填入 API Key")
        sys.exit(1)
    return provider


def demo_memory(llm: LLMClient):
    """① 多轮对话：验证消息历史让模型记得上文。"""
    print("=" * 52)
    print("① 多轮对话：消息就是状态")
    print("=" * 52)
    session = ChatSession(llm, system="你是一个简洁的中文助手，回答不超过一句话。")
    for turn in ["我叫小明，今年 24 岁。", "我最喜欢的编程语言是 Python。", "我叫什么名字？多大了？"]:
        reply = session.ask(turn)
        print(f"用户：{turn}")
        print(f"模型：{reply}\n")
    print(f"(此刻历史里有 {len(session.messages)} 条消息，{session.turns} 个回合)\n")


def demo_tokens(llm: LLMClient):
    """② Token 与成本：观察每轮 prompt_tokens 怎么滚雪球。"""
    print("=" * 52)
    print("② Token 与成本：多轮对话的隐藏账单")
    print("=" * 52)
    session = ChatSession(llm)
    for i in range(1, 4):
        before = session.total_usage["prompt_tokens"]
        session.ask(f"第 {i} 问：用一句话介绍你自己。")
        after = session.total_usage["prompt_tokens"]
        print(f"第 {i} 轮 prompt_tokens 增量: +{after - before}")
    print(f"\n三轮累积用量: {session.total_usage}")
    print("💡 每轮都把全部历史重发给模型——这就是多轮对话成本越滚越大的原因\n")


def demo_truncate(llm: LLMClient):
    """③ 截断治理：truncate 前后对比，便宜但模型会忘事。"""
    print("=" * 52)
    print("③ 历史治理第一刀：截断")
    print("=" * 52)
    session = ChatSession(llm)
    session.ask("我叫小明。")
    session.ask("1+1=？")
    session.ask("2+2=？")
    print(f"截断前：{len(session.messages)} 条消息")
    session.truncate(keep_last_n=2)  # 只留最近 1 轮，「我叫小明」被丢掉
    print(f"截断后：{len(session.messages)} 条消息")
    reply = session.ask("我叫什么名字？")
    print(f"模型：{reply}")
    print("💡 便宜、快，但早期记忆没了——第 08 章 Context 治理会解决这个矛盾")


def main():
    provider = check_env()
    print(f"✅ 环境自检通过：provider={provider}\n")
    llm = LLMClient()
    demo_memory(llm)
    demo_tokens(llm)
    demo_truncate(llm)


if __name__ == "__main__":
    main()
