"""08_context_governance.py —— 第 08 章案例：Context 治理（压缩 / 取舍 / 按需读取）

运行方式（仓库任意子目录）：
    python examples/08_context_governance.py

演示结构：①–④ 纯治理层，无需 API Key；⑤ 走真实 LLM 压缩，需要 .env.
    1. estimate_tokens + keep_last_turns：估算预算、按轮成对裁（不再以 assistant 开头）
    2. select_by_budget：按 token 预算取舍（丢最旧的，保留最新）
    3. compact：旧历史压成摘要 + 最近 N 轮原文（FakeLLM 确定性演示结构）
    4. ReferenceLibrary：按需读取——上下文放目录，需要时才拉全文
    5. 真实 LLM 压缩一段长对话（看 token 从几百压到几十）
"""

import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import (
    LLMClient, ChatSession,
    estimate_tokens, keep_last_turns, compact, select_by_budget, ReferenceLibrary,
)
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


# ---------- 演示用数据 ----------

def fake_history():
    """一段 5 轮的对话历史（system + 10 条），用于治理演示。"""
    return [
        {"role": "system", "content": "你是旅行规划助手。"},
        {"role": "user", "content": "我想去日本玩 5 天，预算 1 万。"},
        {"role": "assistant", "content": "好的，先问几个问题：你更喜欢城市还是自然？"},
        {"role": "user", "content": "城市为主，大阪和东京都想看看。"},
        {"role": "assistant", "content": "那建议大阪 2 天 + 东京 3 天，中间新干线。"},
        {"role": "user", "content": "新干线票要提前买吗？"},
        {"role": "assistant", "content": "旺季建议提前订，可以买 JR Pass 更划算。"},
        {"role": "user", "content": "语法提醒一下，帮我记住：住宿选在心斋桥附近。"},
        {"role": "assistant", "content": "记下了：住宿选在心斋桥附近。"},
        {"role": "user", "content": "最后问一句，现金要换多少？"},
        {"role": "assistant", "content": "建议换 3000 元等值日元，其余刷卡。"},
    ]


class FakeSummarizer:
    """确定性摘要器：返回一个占位摘要，演示 compact 的「结构」而非「质量」。"""
    def chat(self, messages, **kwargs):
        class R:
            content = "用户计划去日本玩5天，预算1万，城市为主(大阪2天+东京3天)，住宿心斋桥附近，已问新干线/现金等细节。"
            usage = {}
        return R()


# ---------- demo ----------

def demo_estimate_and_turns():
    """① 估算 token + 按轮成对裁。"""
    print("=" * 60)
    print("① estimate_tokens + keep_last_turns：预算估算、按轮成对裁")
    print("=" * 60)
    hist = fake_history()
    print(f"  全程 {len(hist)} 条消息 ≈ {estimate_tokens(hist)} tokens")
    # 按轮裁：保留最近 2 轮
    kept = keep_last_turns(hist, turns=2)
    roles = [m["role"] for m in kept]
    print(f"  keep_last_turns(2) → {roles}")
    print("  首条是 system、随后以 user 开头——不会从半轮(assistant)开始\n")
    # 对照第 02 章 truncate 的老问题
    rest = [m for m in hist if m["role"] != "system"]
    odd_cut = ["system"] + rest[-3:]   # 模拟旧版按条数裁 3 条
    print(f"  旧版『按条数裁 3 条』会以 {odd_cut[1]['role']} 开头（半轮）→ 角色顺序报错风险")


def demo_budget():
    """② select_by_budget：按预算取舍。"""
    print("\n" + "=" * 60)
    print("② select_by_budget：预算内挑最有用的 tokens")
    print("=" * 60)
    hist = fake_history()
    before = estimate_tokens(hist)
    slim = select_by_budget(hist, max_tokens=60)
    print(f"  压缩前 {before} tokens → 压缩后 {estimate_tokens(slim)} tokens")
    print(f"  保留条数：{len(slim)} / {len(hist)}，首条角色：{slim[0]['role']}")
    print("  语义：从最新往旧塞，直到预算满；以「越新越相关」为相关性代理\n")


def demo_compact():
    """③ compact：旧历史压摘要 + 近 N 轮原文（FakeLLM）。"""
    print("=" * 60)
    print("③ compact：把 80% 的内容压成 5% 的 token")
    print("=" * 60)
    hist = fake_history()
    slim = compact(FakeSummarizer(), hist, keep_last_turns_n=2)
    for m in slim:
        content = m["content"].replace("\n", " ")
        print(f"  [{m['role']:9}] {content[:56]}{'…' if len(content) > 56 else ''}")
    before, after = len(hist), len(slim)
    print(f"  {before} 条消息 → {after} 条（摘要 1 条 + 最近 2 轮原文）\n")


def demo_reference():
    """④ ReferenceLibrary：上下文放目录，需要时才拉全文。"""
    print("=" * 60)
    print("④ 按需读取：上下文放『目录』，需要时才拉全文")
    print("=" * 60)
    lib = ReferenceLibrary({
        "ref-1": "大阪心斋桥住宿攻略：" + "心斋桥是购物与夜生活中心，" * 20,
        "ref-2": "JR Pass 使用说明：" + "全国版可通乘 JR 线，但部分新干线除外，" * 20,
    })
    catalog = lib.catalog()
    print(f"  目录占 token：{estimate_tokens([{'role': 'user', 'content': catalog}])}")
    print("  （进上下文的是上面这段短目录，不是全文）")
    full = lib.fetch("ref-1")
    print(f"  拉全文 ref-1（{len(full)} 字符）才进上下文；fetch 调用次数：{lib._fetch_count}")
    print("  要点：大而冷的内容存『引用』，需要时才拉全文——这就是 RAG 的最小雏形\n")


def demo_real_compact(llm: LLMClient):
    """⑤ 真实 LLM 压缩。"""
    print("=" * 60)
    print("⑤ 真实 LLM：把一段长对话压成摘要")
    print("=" * 60)
    hist = fake_history()
    print(f"  原始：{len(hist)} 条 ≈ {estimate_tokens(hist)} tokens")
    slim = compact(llm, hist, keep_last_turns_n=1)
    summary_line = [m for m in slim if m["role"] != "system" and m["content"].startswith("【前文摘要】")]
    print(f"  压缩后：{len(slim)} 条 ≈ {estimate_tokens(slim)} tokens")
    if summary_line:
        print(f"  摘要：{summary_line[0]['content'][:90]}…")
    print("\n💡 摘要的质量不如『结构』重要：旧对话的语义被浓缩成几十个 token，")
    print("   而最近一轮的原文原样保留，模型既能记得来龙去脉，又不用为过程废话付费。\n")


def main():
    print()
    demo_estimate_and_turns()
    demo_budget()
    demo_compact()
    demo_reference()

    provider = check_env()
    if not provider:
        return
    print(f"✅ 环境自检通过：provider={provider}\n")
    demo_real_compact(LLMClient())


if __name__ == "__main__":
    main()