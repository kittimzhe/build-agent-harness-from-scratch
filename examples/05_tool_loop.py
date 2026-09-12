"""05_tool_loop.py —— 第 05 章案例：手写第一个工具循环

运行方式（仓库任意子目录都行）：
    python examples/05_tool_loop.py           # 离线段：确定性替身，无需 API Key
    python examples/05_tool_loop.py --real    # 真实模型段：需 .env 配好 API Key

演示：
    离线段（照第 13 章的确定性替身，看的是**循环的形态**——消息怎么一轮轮滚）：
        ① 单轮工具调用：要工具 → 执行 → 给出最终回答
        ② 多轮链式：替身真的读 Observation 算出下一轮的参数（Observation 喂回
           下一轮 Thought 的最小证明，不需要真模型）
        ③ 护栏：把 max_rounds 压到 1，看死循环风险怎么被硬停
    --real 段（同样的三幕，换成真模型自己决定何时用工具）：
        ④⑤⑥ 真实 Function Calling：单轮 / 链式 / 护栏
"""

import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv, find_dotenv

# 找到仓库根目录的 .env（案例可在任意子目录运行）
load_dotenv(find_dotenv(usecwd=True))

# 让脚本能 import 仓库根目录的 harness 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import AgentLoop, LLMClient, LLMResult, Tool
from harness.llm import PROVIDERS


def check_env() -> str:
    """环境自检（提供商表直接读内核的 PROVIDERS，不重复维护）。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未检测到 {key_env}：--real 段需要 API Key（离线段直接跑即可，无需参数）")
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


# ---------- 离线替身：不看 API、只看消息流，照样把循环滚起来 ----------

class SingleToolLLM:
    """① 单轮：第一轮要一次 add，第二轮收尾。"""
    def chat(self, messages, **kwargs):
        if messages and messages[-1].get("role") == "tool":
            return LLMResult(content="1234 + 5678 = 6912（工具算的）", tool_calls=[])
        return LLMResult(content=None, tool_calls=[{
            "id": "call_1", "type": "function",
            "function": {"name": "add", "arguments": '{"a": 1234, "b": 5678}'},
        }])


class ChainedLLM:
    """② 链式替身：真的读 Observation 推出下一步——证明循环在滚，而非摆拍。

    第 1 轮：请求 get_current_time
    第 2 轮：从 Observation（"2026-09-07 21:35:12"）解析时分 → 请求 add(时*60, 分)
    第 3 轮：拿 add 的结果收尾
    """
    def chat(self, messages, **kwargs):
        last = messages[-1] if messages else None
        if last and last.get("role") == "tool":
            prev_call = messages[-2]["tool_calls"][0]["function"]
            if prev_call["name"] == "get_current_time":
                hh, mm = last["content"].split()[1].split(":")[:2]
                h, m = int(hh), int(mm)
                return LLMResult(content=None, tool_calls=[{
                    "id": "call_2", "type": "function",
                    "function": {"name": "add",
                                 "arguments": json.dumps({"a": h * 60, "b": m})},
                }])
            return LLMResult(
                content=f"今天已经过了 {last['content']} 分钟——第 2 轮的 add 参数"
                        f"来自第 1 轮工具结果，这就是 Observation 喂回下一轮",
                tool_calls=[],
            )
        return LLMResult(content=None, tool_calls=[{
            "id": "call_1", "type": "function",
            "function": {"name": "get_current_time", "arguments": "{}"},
        }])


class EndlessToolLLM:
    """③ 永远要工具：给护栏一个必须出场的对手。"""
    def chat(self, messages, **kwargs):
        return LLMResult(content=None, tool_calls=[{
            "id": "call_x", "type": "function",
            "function": {"name": "get_current_time", "arguments": "{}"},
        }])


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


# ---------- 离线段 ①–③ ----------

def demo_single_round_offline():
    print("=" * 56)
    print("① 单轮工具调用：替身要 add → 工具执行 → 收尾（无 API）")
    print("=" * 56)
    loop = AgentLoop(SingleToolLLM(), tools=make_tools(), max_rounds=4)
    out = loop.run("用工具算一下 1234 加 5678 等于多少")
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    show_trace(out)
    print()


def demo_multi_round_offline():
    print("=" * 56)
    print("② 多轮链式：替身读 Observation 算出下一轮参数（无 API）")
    print("=" * 56)
    loop = AgentLoop(ChainedLLM(), tools=make_tools(), max_rounds=6)
    out = loop.run("先查一下现在几点，然后算出今天过了多少分钟")
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    show_trace(out)
    print()


def demo_guardrail_offline():
    print("=" * 56)
    print("③ 护栏：max_rounds=1 时，永远要工具的模型被硬停")
    print("=" * 56)
    loop = AgentLoop(EndlessToolLLM(), tools=make_tools(), max_rounds=1)
    out = loop.run("先查一下现在几点，然后算出今天过了多少分钟")
    print(f"最终回答：{out['reply'][:80]}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    print("💡 没有护栏，一个反复要工具的模型会把你的账单烧穿\n")


# ---------- --real 段 ④–⑥：同样的三幕，真模型自己决定 ----------

def demo_single_round(llm: LLMClient):
    print("=" * 56)
    print("④ 单轮工具调用（真实模型）：模型自己决定用 add")
    print("=" * 56)
    loop = AgentLoop(llm, tools=make_tools(), max_rounds=4)
    out = loop.run("用工具算一下 1234 加 5678 等于多少")
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    show_trace(out)
    print()


def demo_multi_round(llm: LLMClient):
    print("=" * 56)
    print("⑤ 多轮链式（真实模型）：先查时间 → 再用结果算账")
    print("=" * 56)
    loop = AgentLoop(llm, tools=make_tools(), max_rounds=6)
    out = loop.run(
        "先查一下现在几点，然后用 add 工具算出今天过了多少分钟（小时乘 60 再加分钟）"
    )
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    show_trace(out)
    print("💡 对比 ②：替身是照规则读 Observation，真模型是真的在推理\n")


def demo_guardrail(llm: LLMClient):
    print("=" * 56)
    print("⑥ 护栏（真实模型）：max_rounds=1 时，链式任务被硬停")
    print("=" * 56)
    loop = AgentLoop(llm, tools=make_tools(), max_rounds=1)
    out = loop.run("先查一下现在几点，然后用 add 工具算出今天过了多少分钟")
    print(f"最终回答：{out['reply']}")
    print(f"轮数：{out['rounds']}，终止方式：{out['stopped_by']}")
    print("💡 没有护栏，一个反复要工具的模型会把你的账单烧穿\n")


def main():
    want_real = "--real" in sys.argv[1:]

    print("离线段（确定性替身，无需 API Key）——看循环的**形态**：")
    print("谁在哪一轮说了什么、Observation 怎么喂回下一轮、护栏何时出场。\n")
    demo_single_round_offline()
    demo_multi_round_offline()
    demo_guardrail_offline()
    print("✅ 离线段完成。想看真模型自己决定何时用工具：python examples/05_tool_loop.py --real")

    if not want_real:
        return
    print()
    provider = check_env()
    print(f"✅ 环境自检通过：provider={provider}\n")
    llm = LLMClient()
    demo_single_round(llm)
    demo_multi_round(llm)
    demo_guardrail(llm)


if __name__ == "__main__":
    main()
