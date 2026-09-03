"""14_trace.py —— 第 14 章案例：可观测 Trace / 日志 / 回放

运行方式（仓库任意子目录）：
    python examples/14_trace.py

演示 ①–④ 用 FakeLLM 确定性输出、无需 API Key；⑥ 走真实 LLM。

演示结构：
    1. log：结构化事件序列（NDJSON 行）
    2. metric：聚合出这单的健康指标
    3. trace：人读时间线
    4. replay：ScriptedLLM 用录下的响应离线重放 → 结果一致
    5. 接入 Langfuse：hook 就是接入点（思路，不引外部依赖）
    6. 真实 LLM：带 Trace 的一单（需 API）
"""

import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import MiniAgent, Tool, Tracer, ScriptedLLM, LLMClient, LLMResult
from harness.llm import PROVIDERS


def check_env() -> str:
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未配置 {key_env}\n   → 先跑 demo①–④（无需 API）；demo⑥ 需先复制 .env-example 为 .env")
        return ""
    return provider


class OneToolLLM:
    """确定性 LLM：第一轮要一次工具，第二轮给终答。"""
    def __init__(self):
        self.calls = 0
    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return LLMResult(content=None, tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
            }])
        return LLMResult(content="1 + 2 = 3", tool_calls=[])


def add(a: float, b: float) -> float:
    """两数相加"""
    return a + b


def make_traced_agent(llm):
    tracer = Tracer(wrap=llm, name="calc")
    agent = MiniAgent(llm=tracer.llm, system="你是计算器",
                      tools=[Tool(add)], name="calc", max_rounds=8)
    agent.on(tracer.on_event)
    return agent, tracer


# ---------- demo ----------

def demo_log():
    """① log：结构化事件序列。"""
    print("=" * 60)
    print("① log：结构化事件（NDJSON，机器可读、人可 grep）")
    print("=" * 60)
    agent, tracer = make_traced_agent(OneToolLLM())
    agent.run("算 1+2")
    for line in tracer.to_lines():
        print("  " + line)
    print()


def demo_metric():
    """② metric：健康指标。"""
    print("=" * 60)
    print("② metric：从事件聚合出这单的健康指标")
    print("=" * 60)
    agent, tracer = make_traced_agent(OneToolLLM())
    agent.run("算 1+2")
    m = tracer.metrics()
    print(f"  events={m['events']}  rounds={m['rounds']}  tool_calls={m['tool_calls']}")
    print(f"  duration_ms={m['duration_ms']}  final_state={m['final_state']}")
    print("  （rounds=2 因为要了一次工具；final_state=done 因为模型自然收尾）\n")


def demo_timeline():
    """③ trace：人读时间线。"""
    print("=" * 60)
    print("③ trace：时间线")
    print("=" * 60)
    agent, tracer = make_traced_agent(OneToolLLM())
    agent.run("算 1+2")
    print(tracer.timeline())
    print()


def demo_replay():
    """④ replay：ScriptedLLM 离线重放。"""
    print("=" * 60)
    print("④ replay：把录下的 LLM 响应序列，用 ScriptedLLM 离线重放")
    print("=" * 60)
    agent, tracer = make_traced_agent(OneToolLLM())
    out1 = agent.run("算 1+2")
    script = tracer.llm_script()
    print(f"  第一遍：reply={out1['reply']}，录下 {len(script)} 个 LLMResult")

    # 用 ScriptedLLM 重放：不碰真实模型，结果一致
    replayed = MiniAgent(llm=ScriptedLLM(script), system="你是计算器",
                         tools=[Tool(add)], name="replay")
    out2 = replayed.run("算 1+2")
    print(f"  重放  ：reply={out2['reply']}")
    print(f"  一致？{out1['reply'] == out2['reply']}（重放的威力：离线复现问题）\n")


def demo_langfuse_hook():
    """⑤ 接入 Langfuse：hook 就是接入点。"""
    print("=" * 60)
    print("⑤ 接入 Langfuse：Tracer 的事件，就是现成的接入点")
    print("=" * 60)
    print("  Langfuse 的 SDK 也是 span 化记录（trace→generation/span）。")
    print("  我们 Tracer.record 出的每条事件，都可以映射成它的 span：")
    print("    run.start → trace 开始；llm.call/return → generation span；")
    print("    tool_calls 计数 → span 的 input/output 元数据。")
    print("  换它们 SDK 的 callback，还是同一个 hook 思路——本章不引外部依赖，")
    print("  先把『该记什么』立住，剩下的只是『记到哪』的选择。\n")


def demo_real_trace(llm: LLMClient):
    """⑥ 真实 LLM 带 trace。"""
    print("=" * 60)
    print("⑥ 真实 LLM：带 Trace 的一单（需 API）")
    print("=" * 60)
    agent, tracer = make_traced_agent(llm)
    out = agent.run("请算 37 加 5")
    print(tracer.timeline())
    print(f"\n  回复：{out['reply']}\n  指标：{tracer.metrics()}\n")


def main():
    print()
    demo_log()
    demo_metric()
    demo_timeline()
    demo_replay()
    demo_langfuse_hook()

    provider = check_env()
    if not provider:
        return
    print(f"✅ 环境自检通过：provider={provider}\n")
    demo_real_trace(LLMClient())


if __name__ == "__main__":
    main()