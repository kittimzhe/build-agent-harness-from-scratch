"""13_runtime.py —— 第 13 章案例：封装 Mini Agent Runtime

运行方式（仓库任意子目录）：
    python examples/13_runtime.py

演示 ①–③ 用 FakeLLM 确定性输出、无需 API Key；⑤ 走真实 LLM。

演示结构：
    1. 状态机：new → running → done；reset() 回到 new 复用
    2. 事件循环 + 钩子：on_event 观察每一步（FakeLLM 一次工具调用后收尾）
    3. 护栏：模型永远要工具 → max_rounds 硬停 → state=error
    4. 对比 LangGraph / OpenAI Agents SDK：mini runtime 在什么位置
    5. 真实 LLM：把前面九块砖装进一个 MiniAgent（需 API）
"""

import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import MiniAgent, AgentState, Tool, LLMClient, LLMResult
from harness.llm import PROVIDERS


def check_env() -> str:
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未配置 {key_env}\n   → 先跑 demo①–③（无需 API）；demo⑤ 需先复制 .env-example 为 .env")
        return ""
    return provider


class StaticLLM:
    """确定性 LLM：永远直接给终答（不走工具）。"""
    def chat(self, messages, **kwargs):
        return LLMResult(content="你好，周报已准备好（演示状态机）。", tool_calls=[])


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


class EndlessToolLLM:
    """确定性 LLM：永远要工具（永不收尾），用来触发 max_rounds 护栏。"""
    def chat(self, messages, **kwargs):
        return LLMResult(content=None, tool_calls=[{
            "id": "call_1", "type": "function",
            "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'},
        }])


def add(a: float, b: float) -> float:
    """两数相加"""
    return a + b


# ---------- demo ----------

def demo_state_machine():
    """① 状态机 + reset。"""
    print("=" * 60)
    print("① 状态机：new → running → done；reset() 回到 new")
    print("=" * 60)
    agent = MiniAgent(llm=StaticLLM(), system="你是助手", name="demo", max_rounds=8)
    print(f"  初始 state = {agent.state}")
    out = agent.run("打个招呼")
    print(f"  run 后 state = {agent.state} | reply = {out['reply'][:20]}…")
    agent.reset()
    print(f"  reset 后 state = {agent.state}（可复用跑下一单）\n")


def demo_events_and_hooks():
    """② 事件循环 + 钩子。"""
    print("=" * 60)
    print("② 事件循环 + 钩子：on_event 观察每一步")
    print("=" * 60)
    prints = []
    agent = MiniAgent(llm=OneToolLLM(), system="你是计算器",
                      tools=[Tool(add)], name="calc", max_rounds=8)
    agent.on(lambda e: prints.append(f"{e.type}"))
    out = agent.run("算 1+2")
    print(f"  钩子捕获的事件序列：{' → '.join(prints)}")
    print(f"  state={agent.state}，reply={out['reply']}，rounds={out['rounds']}")
    print("  （这些事件就是第 14 章 trace 要系统化收集/回放的东西）\n")


def demo_guardrail():
    """③ 护栏 → error 状态。"""
    print("=" * 60)
    print("③ 护栏：模型永远要工具 → max_rounds 硬停 → state=error")
    print("=" * 60)
    agent = MiniAgent(llm=EndlessToolLLM(), system="你是计算器",
                      tools=[Tool(add)], name="calc", max_rounds=3)
    out = agent.run("算 1+2")
    print(f"  state={agent.state}")
    print(f"  reply={out['reply'][:40]}…")
    ev = agent.events[-1]
    print(f"  最后事件 type={ev.type}，payload={ev.payload}\n")


def demo_vs_frameworks():
    """④ 对比 LangGraph / OpenAI Agents SDK。"""
    print("=" * 60)
    print("④ 对比：mini runtime 在「框架」面前的什么位置")
    print("=" * 60)
    print("  LangGraph：把 Agent 的每一步流转显式图化（node + edge），可视化、可分支。")
    print("  OpenAI Agents SDK：handoff（agent 之间转交）+ guardrail + tracing 一等公民。")
    print("  本教程 MiniAgent：一条循环 + 显式状态字段 + 钩子，最薄但价值观一致。")
    print("   ——显式状态、可插拔、可观察。看懂了它，再看框架就是『替你写好了这些』。\n")


def demo_real_agent(llm: LLMClient):
    """⑤ 真实 LLM。"""
    print("=" * 60)
    print("⑤ 真实 LLM：九块砖装进一个 MiniAgent")
    print("=" * 60)
    agent = MiniAgent(llm=llm, system="你是乐于助人的助手", tools=[Tool(add)], name="real")
    agent.on(lambda e: print(f"  [事件] {e.type}"))
    out = agent.run("请算一下 37 加 5 等于多少，直接给结论")
    print(f"\n  state={agent.state}，回复：{out['reply']}\n")


def main():
    print()
    demo_state_machine()
    demo_events_and_hooks()
    demo_guardrail()
    demo_vs_frameworks()

    provider = check_env()
    if not provider:
        return
    print(f"✅ 环境自检通过：provider={provider}\n")
    demo_real_agent(LLMClient())


if __name__ == "__main__":
    main()