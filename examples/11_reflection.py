"""11_reflection.py —— 第 11 章案例：失败策略与反思（Self-Reflection）

运行方式（仓库任意子目录）：
    python examples/11_reflection.py

演示 ①–④ 用 FakeReflector 确定性输出、无需 API Key；⑤ 走真实 LLM 反思。

演示结构：
    1. 傻重试 vs 聪明重试：第 06 章 RetryPolicy 同动作重来 vs 本章反思换思路
    2. reflect：把失败回喂给模型，拿回结构化反思（FakeReflector）
    3. retry_with_reflection：失败两次后换思路成功（确定性循环）
    4. 反思融入 Planning：第 10 章计划某步失败 → 反思决定重规划
    5. 真实 reflect：让真模型反思一次失败并给改法（需 API）
"""

import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import (
    reflect, retry_with_reflection, Plan, RetryPolicy, LLMClient,
)
from harness.llm import PROVIDERS


def check_env() -> str:
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    if provider not in PROVIDERS:
        print(f"❌ 未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}")
        sys.exit(1)
    key_env = PROVIDERS[provider][0]
    if not os.getenv(key_env) and provider != "ollama":
        print(f"❌ 未配置 {key_env}\n   → 先跑 demo①–④（无需 API）；demo⑤ 需先复制 .env-example 为 .env")
        return ""
    return provider


class FakeReflector:
    """确定性反思器：固定返回「换思路再试」，演示反思的结构而非质量。"""
    def chat(self, messages, **kwargs):
        class R:
            content = ('{"verdict": "retry", "reason": "当前思路被证明走不通",'
                       ' "next_action": "改成从官网开放接口去查，而不是内网直连"}')
        return R()


# ---------- demo ----------

def demo_stupid_vs_smart():
    """① 傻重试 vs 聪明重试。"""
    print("=" * 60)
    print("① 第 06 章『傻重试』vs 本章『反思式重试』")
    print("=" * 60)
    print("  傻重试（RetryPolicy）：同一个动作、退避重来")
    print("     只挡瞬时故障：超时 / 限流 / 网络抖动；动作错了重试一万次也没用")
    print("  聪明重试（retry_with_reflection）：失败 → 反思 → 换思路 → 再试")
    print("     挡『思路错了』：让模型自己判断改什么\n")
    # 演示 RetryPolicy 的样子（不真跑网络）
    p = RetryPolicy(max_retries=3, base_delay=0.01)
    print(f"  RetryPolicy 的语义：max_retries={p.max_retries}（同一动作再试 3 次），"
          f"base_delay={p.base_delay}s 退避\n")


def demo_reflect():
    """② reflect：结构化反思。"""
    print("=" * 60)
    print("② reflect：把失败回喂给模型，拿回结构化反思")
    print("=" * 60)
    r = reflect(FakeReflector(), "查订单 42 的物流", "上次尝试：内网直连超时")
    print(f"  verdict     = {r.verdict}")
    print(f"  reason      = {r.reason}")
    print(f"  next_action = {r.next_action}")
    print("  （FakeReflector 固定返回；复用第 07 章结构化输出）\n")


def demo_retry_loop():
    """③ retry_with_reflection：失败两次后换思路成功。"""
    print("=" * 60)
    print("③ retry_with_reflection：失败 → 反思 → 换思路 → 再试")
    print("=" * 60)

    def attempt_fn(current_goal):
        # 只有「换思路后的目标」才能成功——模拟「原思路怎么试都失败」
        if "官网开放接口" not in current_goal:
            raise RuntimeError("内网直连被拒：Connection refused")
        return "查到了：物流单在派送中"

    res = retry_with_reflection(FakeReflector(), "查订单 42 的物流", attempt_fn, max_reflections=2)
    for a in res.attempts:
        tag = "✅" if a["outcome"] == "success" else "❌"
        line = f"  {tag} 第{a['attempt']}次 goal={a['goal'][:22]}…"
        if a["outcome"] == "success":
            line += f" → {a['result']}"
        else:
            line += f" → {a['error']}，反思 verdict={a.get('verdict')}"
        print(line)
    print(f"  最终 success={res.success}，结果：{res.result}\n")


def demo_reflection_in_planning():
    """④ 反思融入 Planning：计划某步失败 → 反思决定重规划。"""
    print("=" * 60)
    print("④ 反思融入 Planning：计划步骤失败，模型决定下一步")
    print("=" * 60)
    plan = Plan(goal="出周报", steps=["拉订单数据", "算总额", "画图"])
    # 第 0 步失败后，让反思决定「这一步怎么办」
    step0 = plan[0]
    print(f"  计划第 0 步『{step0.description}』执行失败 → 反思给改法：")
    r = reflect(FakeReflector(), step0.description, "数据库连不上")
    print(f"    {r.verdict}：{r.next_action}")
    step0.status = "failed"
    step0.result = r.next_action
    print("   （第 12 章会把这个 failed + 改法 序列化，断点续跑从这里继续）\n")


def demo_real_reflect(llm: LLMClient):
    """⑤ 真实反思。"""
    print("=" * 60)
    print("⑤ 真实 LLM：反思一次失败并给改法")
    print("=" * 60)
    r = reflect(llm, "给全公司发一封全员邮件", "上次尝试：邮箱 SMTP 认证失败，530 Authentication required")
    print(f"  verdict     = {r.verdict}")
    print(f"  reason      = {r.reason}")
    print(f"  next_action = {r.next_action}")
    print()
    print("💡 观察反思的质量：不是『再试一次』这种废话，而是指出具体哪里错了、")
    print("   下一步该怎么改。这才是 Self-Reflection 和「傻重试」的分水岭。\n")


def main():
    print()
    demo_stupid_vs_smart()
    demo_reflect()
    demo_retry_loop()
    demo_reflection_in_planning()

    provider = check_env()
    if not provider:
        return
    print(f"✅ 环境自检通过：provider={provider}\n")
    demo_real_reflect(LLMClient())


if __name__ == "__main__":
    main()