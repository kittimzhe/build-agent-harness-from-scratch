"""05_tool_loop.py —— 第 05 章案例：手写第一个工具循环

运行方式（在仓库任意子目录都行）：
    python examples/05_tool_loop.py

演示：
    1. 单轮工具调用：模型要工具 → 执行 → 给出最终回答
    2. 多轮链式：先查时间，再用查到的结果算账（真正的 Thought→Action→Observation）
    3. 护栏：把 max_rounds 压到 1，看死循环风险怎么被硬停
"""

import os
import sys
from datetime import datetime

from dotenv import load_dotenv, find_dotenv

# 找到仓库根目录的 .env（案例可在任意子目录运行）
load_dotenv(find_dotenv(usecwd=True))

# 让脚本能 import 仓库根目录的 harness 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import AgentLoop, LLMClient, Tool
from harness.llm import PROVIDERS


def check_env() -> str:
    """环境自检（提供商表直接读内核的 PROVIDERS，不重复维护）。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未检测到 {key_env}，请先复制 .env-example 为 .env 并填入 API Key")
        sys.exit(1)
    return provider


# ---------- 三个演示用的工具：纯函数、无外部依赖 ----------

def get_current_time() -> str:
    """获取当前的本地时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add(a: float, b: float) -> float:
    """两数相加"""
    return a + b


def multiply(a: float, b: float) -> float:
    """两数相乘"""
    return a * b


def make_tools() -> list[Tool]:
    """把普通函数包装成模型可调用的 Tool（带参数 schema）。"""
    return [
        Tool(get_current_time),
        Tool(add, parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        }),
        Tool(multiply, parameters={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        }),
    ]


def show_trace(out: dict):
    """打印这次任务的执行轨迹：谁说的、调了什么工具。"""
    print("  执行轨迹（消息列表）：")
    for m in out["messages"]:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                print(f"    🤖 assistant  → 请求工具 {tc['function']['name']}({tc['function']['arguments']})")
        elif role == "tool":
            print(f"    🔧 tool       → {m['content']}")
        elif role == "assistant":
            print(f"    🤖 assistant  → {m['content'][:60]}")
        else:
            print(f"    👤 {role:11} → {str(m['content'])[:60]}")


def demo_single_round(loop: AgentLoop):
    """① 单轮工具调用。"""
    print("=" * 56)
    print("① 单轮工具调用：模型自己决定用 add")
    print("=" * 56)
    out = loop.run("用工具算一下 1234 加 5678 等于多少")
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    show_trace(out)
    print()


def demo_multi_round(llm: LLMClient):
    """② 多轮链式：先查时间，再拿查到的结果去计算。"""
    print("=" * 56)
    print("② 多轮链式：先查时间 → 再用结果算账")
    print("=" * 56)
    loop = AgentLoop(llm, tools=make_tools(), max_rounds=6)
    out = loop.run(
        "先查一下现在几点，然后用 add 工具算出今天过了多少分钟（小时乘 60 再加分钟）"
    )
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    show_trace(out)
    print("💡 第 2 轮的 add 参数来自第 1 轮工具结果——这就是 Observation 喂回下一轮 Thought\n")


def demo_guardrail(llm: LLMClient):
    """③ 护栏：max_rounds=1，任务没做完就被硬停。"""
    print("=" * 56)
    print("③ 护栏：max_rounds=1 时，链式任务被硬停")
    print("=" * 56)
    loop = AgentLoop(llm, tools=make_tools(), max_rounds=1)
    out = loop.run("先查一下现在几点，然后用 add 工具算出今天过了多少分钟")
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    print("💡 没有护栏，一个反复要工具的模型会把你的账单烧穿\n")


def main():
    provider = check_env()
    print(f"✅ 环境自检通过：provider={provider}\n")
    llm = LLMClient()
    demo_single_round(AgentLoop(llm, tools=make_tools()))
    demo_multi_round(llm)
    demo_guardrail(llm)


if __name__ == "__main__":
    main()
