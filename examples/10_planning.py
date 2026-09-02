"""10_planning.py —— 第 10 章案例：任务拆解与 Planning（Plan-and-Execute）

运行方式（仓库任意子目录）：
    python examples/10_planning.py

演示 ①–③ 用 FakePlanner 确定性输出、无需 API Key；⑤ 走真实 LLM 出计划。

演示结构：
    1. Plan / PlanStep 数据结构：建计划、推进、打钩看进度
    2. make_plan：复用第 07 章结构化输出，让「LLM」吐步骤清单（FakePlanner）
    3. execute_plan：逐步执行；第 3 步故意失败 → 失败即停
    4. ReAct vs Plan-and-Execute：第 05 章的 AgentLoop 是边想边做，这里是先出清单
    5. 真实 make_plan：让真模型把目标拆成步骤（需 API）
"""

import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Plan, make_plan, execute_plan, LLMClient
from harness.llm import PROVIDERS


def check_env() -> str:
    """环境自检（仅 demo⑤ 需要 API Key）。"""
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未配置 {key_env}\n   → 先跑 demo①–④（无需 API）；demo⑤ 需先复制 .env-example 为 .env")
        return ""
    return provider


class FakePlanner:
    """确定性规划器：返回一份固定的步骤 JSON，演示 make_plan 的结构而非质量。"""
    def chat(self, messages, **kwargs):
        class R:
            content = '{"steps": ["查目的地天气", "订酒店", "买往返票", "写每日行程表", "打包行李"]}'
        return R()


# ---------- demo ----------

def demo_plan_structure():
    """① Plan 数据结构 + 进度打钩。"""
    print("=" * 60)
    print("① Plan：把「计划」变成可推进、可观察的状态")
    print("=" * 60)
    plan = Plan(goal="规划三日旅行", steps=["查天气", "订酒店", "买票", "写行程表"])
    print("  初始计划：")
    for line in plan.progress().splitlines():
        print(f"    {line}")
    first = plan.next_action()
    print(f"  执行指针 next_action → {first.description!r}")
    plan.mark_done(0, "天气晴，21°C")
    print("  完成第 0 步后：")
    for line in plan.progress().splitlines():
        print(f"    {line}")
    print(f"  是否全部完成：{plan.is_complete()}\n")


def demo_make_plan():
    """② make_plan：结构化输出吐步骤清单。"""
    print("=" * 60)
    print("② make_plan：复用结构化输出，把目标拆成步骤清单")
    print("=" * 60)
    plan = make_plan(FakePlanner(), "计划一次日本三日游", max_steps=5)
    print(f"  目标：{plan.goal}")
    for i, s in enumerate(plan, 1):
        print(f"    第{i}步  {s.description}")
    print("  （FakePlanner 固定返回；真实模型见 demo⑤）\n")


def demo_execute():
    """③ execute_plan：逐步执行 + 失败即停。"""
    print("=" * 60)
    print("③ execute_plan：逐步执行；第 3 步失败 → 立即停")
    print("=" * 60)
    plan = Plan(goal="规划三日旅行", steps=["查天气", "订酒店", "买票", "写行程表", "打包"])

    def fake_executor(desc, idx):
        if idx == 2:
            raise RuntimeError("买票接口超时了（模拟第 3 步失败）")
        return f"完成：{desc}"

    results = execute_plan(plan, fake_executor)
    for r in results:
        tag = "✅" if r["status"] == "done" else "❌"
        print(f"  {tag} [{r['index']}] {r['step']} → {r['result']}")
    print("  执行完的进度：")
    for line in plan.progress().splitlines():
        print(f"    {line}")
    print(f"  （失败即停是刻意的——怎么补偿是第 11 章『失败策略与反思』）\n")


def demo_react_vs_pae():
    """④ ReAct vs Plan-and-Execute 的取舍。"""
    print("=" * 60)
    print("④ ReAct vs Plan-and-Execute：一个边想边做，一个先列清单")
    print("=" * 60)
    print("  ReAct（第 05 章 AgentLoop）：")
    print("    think → 调一个工具 → observe → 再 think → … 每轮只决定『下一步』")
    print("    适合：探索性任务、路径不确定、需要边做边看反馈")
    print("  Plan-and-Execute（本章）：")
    print("    make_plan 先出步骤清单 → execute_plan 逐步打钩")
    print("    适合：目标清晰、步骤可预判、要『可审查的计划』和明确进度")
    print("  取舍一句话：计划越好 → P&E 越省；计划越可能错 → 越该回到 ReAct 随时纠偏\n")


def demo_real_plan(llm: LLMClient):
    """⑤ 真实 make_plan。"""
    print("=" * 60)
    print("⑤ 真实 LLM：把目标拆成步骤清单")
    print("=" * 60)
    plan = make_plan(llm, "写一篇介绍 Agent 的公众号推送并发布", max_steps=5)
    print(f"  目标：{plan.goal}")
    for i, s in enumerate(plan, 1):
        print(f"    第{i}步  {s.description}")
    print()
    print("💡 观察这份计划：是一份『你（或另一个 Agent）能照着逐条做』的清单，")
    print("   不是一段散文。这就是 Planning 的价值——先把『做什么』固化，再谈执行。\n")


def main():
    print()
    demo_plan_structure()
    demo_make_plan()
    demo_execute()
    demo_react_vs_pae()

    provider = check_env()
    if not provider:
        return
    print(f"✅ 环境自检通过：provider={provider}\n")
    demo_real_plan(LLMClient())


if __name__ == "__main__":
    main()