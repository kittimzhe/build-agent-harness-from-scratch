"""07_structured_output.py —— 第 07 章案例：结构化输出与 Schema 设计

运行方式（仓库任意子目录）：
    python examples/07_structured_output.py

演示结构：①–③ 纯解析/校验层，无需 API Key；④ 走真实 LLM，需要 .env.
    1. extract_json：从各种「不干净的」模型输出里抠出 JSON
    2. strict_validate：Pydantic 模型校验（类型 / 必填 / 数值约束）
    3. 自纠重试：解析失败 → 把错误回喂 → 模型改正（用 FakeLLM 确定性演示）
    4. 真实 LLM 结构化输出（情绪分析），拿回已验证的 Pydantic 对象
"""

import os
import sys

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import BaseModel, Field
from typing import Literal

from harness import (
    LLMClient, StructuredOutputError, extract_json, strict_validate, structured_chat,
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


# ---------- demo 用的 Pydantic 模型 ----------

class Sentiment(BaseModel):
    """情绪分析结果：shape 就写在类型系统里。"""
    label: Literal["positive", "negative", "neutral"]
    score: float = Field(ge=0.0, le=1.0, description="置信度，0 到 1 之间")
    keywords: list[str]


# ---------- demo ----------

def demo_extract():
    """① extract_json：容忍代码围栏、前后废话。"""
    print("=" * 60)
    print("① extract_json：从不干净的输出里抠 JSON")
    print("=" * 60)
    samples = [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '好的，结果如下：{"a": 1} 希望有帮助',
        '这里是解释，内容是 {"a": 1, "b": [2, 3]}，完毕',
    ]
    for s in samples:
        print(f"  {s[:32]!r:38} → {extract_json(s)}")


def demo_validate():
    """② strict_validate：类型 / 必填 / 数值约束，三类都拦得住。"""
    print("\n" + "=" * 60)
    print("② strict_validate：Pydantic 校验三类失败")
    print("=" * 60)
    cases = [
        ('{"label": "happy", "score": 0.8, "keywords": ["好"]}', "label 不在枚举里"),
        ('{"label": "positive", "score": 85, "keywords": ["好"]}', "score 越界（0-1）"),
        ('{"label": "positive", "score": 0.8}', "缺少 keywords 必填字段"),
    ]
    for text, why in cases:
        try:
            strict_validate(Sentiment, text)
            print(f"  ✅（竟然通过）：{why}")
        except StructuredOutputError as e:
            print(f"  ❌ {why} → {str(e).splitlines()[0][:52]}")
    ok = strict_validate(Sentiment, '{"label": "positive", "score": 0.85, "keywords": ["周到"]}')
    print(f"  ✅ 合法输入 → {ok.model_dump()}")


def demo_self_correct():
    """③ 自纠重试：先给坏答案，被拒后回喂错误，第二次修正（FakeLLM 确定性演示）。"""
    print("\n" + "=" * 60)
    print("③ 自纠重试：解析失败 → 错误回喂 → 模型改正")
    print("=" * 60)

    class FlakyStructuredLLM:
        """第 1 次输出 label 超枚举 + score 越界，第 2 次改正。"""
        def __init__(self):
            self.n = 0

        def chat(self, messages, **kwargs):
            self.n += 1
            content = (
                '{"label": "happy", "score": 85, "keywords": ["好"]}'   # 第 1 次：错
                if self.n == 1 else
                '{"label": "positive", "score": 0.85, "keywords": ["好"]}'  # 第 2 次：对
            )
            class R:
                def __init__(self): self.content = content
                usage = {}
            return R()

    result = structured_chat(FlakyStructuredLLM(), [
        {"role": "user", "content": "分析这句话的情绪：服务很周到。"}
    ], Sentiment, max_retries=2)

    assert result.label == "positive" and result.score == 0.85
    print(f"  最终拿回：{result.model_dump()}")
    print("  说明：第 1 次输出被 Pydantic 拒了，错误作为 user 消息回喂，第 2 次才通过——这就是「自纠」\n")


def demo_real_llm(llm: LLMClient):
    """④ 真实 LLM 结构化输出。"""
    print("=" * 60)
    print("④ 真实 LLM：情绪分析，返回已验证的 Pydantic 对象")
    print("=" * 60)
    text = "等了四十分钟，结果待办还办不了，太气人了"
    result = structured_chat(llm, [
        {"role": "user", "content": f"分析这句话的情绪：{text}"}
    ], Sentiment)
    print(f"  输入：{text}")
    print(f"  分析：{result.model_dump()}")
    print(f"  类型校验通过：label 必为枚举、score 必在 [0,1]")
    print("\n💡 下游拿到的是强类型的 Sentiment 对象，不是一段要再解析的字符串——")
    print("   从这一步起，模型输出才真正接进「程序」的管子里。\n")


def main():
    print()
    demo_extract()
    demo_validate()
    demo_self_correct()

    provider = check_env()
    if not provider:
        return
    print(f"✅ 环境自检通过：provider={provider}\n")
    demo_real_llm(LLMClient())


if __name__ == "__main__":
    main()