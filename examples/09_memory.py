"""09_memory.py —— 第 09 章案例：记忆体系（短期 / 长期 / 向量）

运行方式（仓库任意子目录）：
    python examples/09_memory.py

本章全部 demo 都**不需要 API Key**：记忆是确定性的，玩具嵌入离线可跑——
真实 embedding 只是把 toy_embed 换掉，检索流程不变（见 §2.3 与附录）。

演示结构：
    1. 三层记忆总览：短期(ChatSession) / 长期(FileMemory) / 向量(VectorMemory)
    2. FileMemory：记住 → 落盘 → 「另一个会话」重载取回
    3. VectorMemory：玩具嵌入的语义检索（表面相似）
    4. 玩具嵌入的局限：同义改写就查不到 → 说明真语义要真 embedding
    5. RAG 最小闭环：retrieved_context 把命中的记忆拼进 prompt
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import (
    ChatSession, FileMemory, VectorMemory, toy_embed, cosine, retrieved_context,
)
from harness.llm import PROVIDERS  # noqa: F401  仅证明无需 .env 也能 import


# ---------- demo ----------

def demo_taxonomy():
    """① 三层记忆总览。"""
    print("=" * 60)
    print("① 三层记忆：短期 / 长期 / 向量")
    print("=" * 60)
    # 短期：ChatSession.messages（第 02 章就有了）
    sess = ChatSession(llm=object(), system="你是助手")
    sess.messages += [{"role": "user", "content": "我叫小明"}]
    print(f"  短期记忆　= ChatSession.messages（本会话）→ {len(sess.messages)} 条")
    print("  长期记忆　= FileMemory（跨会话，key→value）")
    print("  向量记忆　= VectorMemory（语义相似检索）\n")


def demo_file_memory():
    """② FileMemory：落盘 / 跨会话重载。"""
    print("=" * 60)
    print("② FileMemory：落盘，另一个会话才记得")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "user_memory.json")
        # 会话 A：记住 + 落盘
        a = FileMemory(path)
        a.remember("user_name", "小明")
        a.remember("prefers", "大阪在心斋桥附近定住宿")
        a.save()
        # 会话 B：重新加载（模拟下次对话 / 另一个进程）
        b = FileMemory(path)
        print(f"  会话 B 取回 user_name：{b.recall('user_name')}")
        print(f"  会话 B 取回 prefers：{b.recall('prefers')}")
        print(f"  会话 B 全部事实：{b.facts()}")
    print("  （TemporaryDirectory 用完即删，生产里给个真实路径）\n")


def demo_vector():
    """③ VectorMemory：玩具嵌入做「表面相似」检索。"""
    print("=" * 60)
    print("③ VectorMemory：按『相似度』找，而不是按 key 精确找")
    print("=" * 60)
    vmem = VectorMemory()
    vmem.add("用户投诉过服务太慢")
    vmem.add("用户想订东京到大阪的新干线票")
    vmem.add("用户偏好住心斋桥附近")
    hits = vmem.search("用户投诉服务太慢，想问问处理进度", top_k=3)
    for h in hits:
        print(f"  score={h['score']}  {h['text']}")
    print("  （玩具嵌入靠字符共现，字面相近时分数高——这是『表面相似』）\n")


def demo_toy_limit():
    """④ 玩具嵌入的局限：语义等价但字面不同就抓不到。"""
    print("=" * 60)
    print("④ 玩具嵌入的局限：语义等价但字面不同就抓不到（为何要真 embedding）")
    print("=" * 60)
    vmem = VectorMemory()
    vmem.add("用户之前问过能不能退钱")
    hits = vmem.search("用户咨询退款政策", top_k=1)
    print(f"  句意都是「能不能退钱」，玩具嵌入只靠『用户』二字给到 {hits[0]['score']}")
    vmem2 = VectorMemory()
    vmem2.add("用户投诉过服务太慢")
    h2 = vmem2.search("用户投诉服务太慢", top_k=1)
    print(f"  而字面几乎逐字相同 → 相似度 {h2[0]['score']}")
    print("  → 玩具嵌入只演示『检索机制』；真语义把 embed= 换成真实 embedding 模型即可\n")


def demo_rag_loop():
    """⑤ RAG 最小闭环：retrieved_context 拼进 prompt。"""
    print("=" * 60)
    print("⑤ RAG 最小闭环：检索命中的记忆 → 拼进上下文")
    print("=" * 60)
    vmem = VectorMemory()
    vmem.add("退款需在 7 天内申请，附订单号")
    vmem.add("改签需付差价")
    ctx = retrieved_context(vmem, "我想退款要怎么办", top_k=1)
    prompt = {"role": "user", "content": ctx + "\n\n请问：用户申请退款需要什么？"}
    print("  拼进 prompt 的内容：")
    for line in prompt["content"].splitlines():
        print(f"    {line}")
    print("  （这就是 RAG 的『检索 → 拼进 prompt』——与 Memory 的『主动写状态』正好相对）\n")


def main():
    print()
    demo_taxonomy()
    demo_file_memory()
    demo_vector()
    demo_toy_limit()
    demo_rag_loop()
    print("✅ 本章全部 demo 无需 API Key，确定性输出完成。")


if __name__ == "__main__":
    main()