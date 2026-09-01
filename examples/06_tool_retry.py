"""06_tool_retry.py —— 第 06 章案例：工具集合与容错

运行方式（仓库任意子目录）：
    python examples/06_tool_retry.py

演示结构：①–③ 纯工具层，无需 API Key；④ 走 AgentLoop，需要 .env.
    1. 重试：瞬时错误在「工具边界」内重试，模型不可见
    2. 超时：卡死的工具不拖垮循环
    3. 幂等：非幂等工具不自动重试 + 幂等键去重
    4. 循环里的重试 vs 不重试：看赚了多少轮 / token
"""

import os
import sys
import time

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import (
    AgentLoop, LLMClient, Tool,
    RetryPolicy, ResilientTool, ToolRegistry, ToolError,
)
from harness.llm import PROVIDERS


def check_env() -> str:
    """环境自检（仅 demo④ 需要 API Key）。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未配置 {key_env}\n   → 先跑 demo①–③（无需 API）；demo④ 需先复制 .env-example 为 .env")
        return ""
    return provider


# ---------- 演示用的工具 ----------

class FlakyAdd:
    """前 fail_times 次调用抛错，之后成功（确定性模拟瞬时抖动）。"""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self, a: float, b: float) -> float:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("服务暂时不可用（模拟瞬时抖动）")
        return a + b


def slow_lookup(keyword: str) -> str:
    """模拟一个很慢的查询工具。"""
    time.sleep(2.0)
    return f"{keyword} 的查询结果"


class OrderCreator:
    """模拟一个【非幂等】工具：重复执行 = 重复下单。"""

    def __init__(self):
        self.orders = []

    def __call__(self, item: str) -> str:
        self.orders.append(item)
        return f"已下单：{item}（第 {len(self.orders)} 单）"


def make_flaky_once() -> dict:
    """demo④ 用：前 1 次失败、之后成功的加法工具。"""
    state = {"calls": 0}

    def flaky(a: float, b: float) -> float:
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("瞬时超时")
        return a + b

    return state, flaky


# ---------- demo ----------

def demo_retry():
    """① 重试：瞬时失败在工具边界内重试，外部无感知。"""
    print("=" * 60)
    print("① 重试：瞬时抖动重试 3 次后成功")
    print("=" * 60)
    flaky = FlakyAdd(fail_times=3)
    tool = ResilientTool(flaky, name="flaky_add", parameters={
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    }, policy=RetryPolicy(max_retries=3, idempotent=True))
    print(f"调用 tool.run(a=1, b=2) → {tool.run(a=1, b=2)}")
    print(f"工具内部实际执行了 {flaky.calls} 次（前 3 次失败自动重试，第 4 次成功）\n")


def demo_timeout():
    """② 超时：卡死的工具被拦下，循环不被拖垮。"""
    print("=" * 60)
    print("② 超时：1 秒预算拦住 2 秒的慢工具")
    print("=" * 60)
    tool = ResilientTool(slow_lookup, name="slow_lookup",
                         policy=RetryPolicy(timeout=1.0))
    try:
        tool.run(keyword="Agent Harness")
    except ToolError as e:
        print(f"捕获 ToolError：{e}\n")


def demo_idempotency():
    """③ 幂等：非幂等不重试；幂等键去重。"""
    print("=" * 60)
    print("③ 幂等：非幂等工具拒重试 + 幂等键去重")
    print("=" * 60)
    # (a) 非幂等工具 + 重试策略 → 第一次失败后拒绝自动重试
    def first_fail_charge(amount: float):
        raise RuntimeError("支付网关抖了一下")

    charge = ResilientTool(first_fail_charge, name="charge",
                           policy=RetryPolicy(max_retries=2, idempotent=False))
    try:
        charge.run(amount=9.9)
    except ToolError as e:
        print(f"(a) 非幂等工具第一次失败后：{e}")

    # (b) 幂等键去重：同一个 idempotency_key 不重复下单
    creator = OrderCreator()
    registry = ToolRegistry()
    registry.register(Tool(creator, name="create_order"), RetryPolicy())
    key = "order-20260826-001"
    r1 = registry.run("create_order", {"item": "咖啡"}, idempotency_key=key)
    r2 = registry.run("create_order", {"item": "咖啡"}, idempotency_key=key)
    print(f"(b) 同幂等键两次下单：\n    第 1 次 → {r1}\n    第 2 次 → {r2}")
    print(f"    OrderCreator 实际执行了 {len(creator.orders)} 次（去重生效，没有二次扣款）\n")


def demo_loop_retry(llm: LLMClient):
    """④ 循环里重试 vs 不重试：看赚了多少轮。"""
    print("=" * 60)
    print("④ 循环里的重试：ResilientTool 让模型不看见瞬时故障")
    print("=" * 60)
    state, flaky = make_flaky_once()
    params = {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    }

    print("--- 对照组：普通 Tool（无重试），失败会回喂给模型 ---")
    plain_loop = AgentLoop(llm, tools=[Tool(flaky, name="add", parameters=params)], max_rounds=4)
    out1 = plain_loop.run("用 add 工具算 2+3")
    print(f"结果：{out1['reply']}")
    print(f"轮数：{out1['rounds']}，工具实际执行：{state['calls']} 次")
    print("（第 1 轮工具失败→错误回喂模型→模型第 2 轮重试→第 3 轮给答案）\n")

    # 重置状态，换 ResilientTool
    state["calls"] = 0
    print("--- 实验组：ResilientTool（重试 1 次，幂等），模型全程只见最终结果 ---")
    rt_loop = AgentLoop(llm, tools=[ResilientTool(flaky, name="add", parameters=params,
                                                  policy=RetryPolicy(max_retries=1, idempotent=True))],
                        max_rounds=4)
    out2 = rt_loop.run("用 add 工具算 2+3")
    print(f"结果：{out2['reply']}")
    print(f"轮数：{out2['rounds']}，工具实际执行：{state['calls']} 次")
    print("（第 1 轮工具在边界内自动重试成功，模型第 2 轮直接给答案）")
    print(f"\n💡 对照组 {out1['rounds']} 轮 vs 实验组 {out2['rounds']} 轮——每省 1 轮 = 少重发全部历史 + 少一次生成\n")


def main():
    print()
    demo_retry()
    demo_timeout()
    demo_idempotency()

    provider = check_env()
    if not provider:
        return  # demo①-③ 已完成，④ 缺少 API Key 就跳过
    print(f"✅ 环境自检通过：provider={provider}\n")
    demo_loop_retry(LLMClient())


if __name__ == "__main__":
    main()