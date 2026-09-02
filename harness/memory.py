"""memory —— 记忆体系（Harness 第七块砖，第 09 章落地）。

第 08 章的 `ReferenceLibrary`（目录 + fetch）只是「按需读取」的雏形。第 09 章把它
长成三层记忆，并回答「什么时候用文件记忆、什么时候用向量记忆」：

1. 短期记忆（short-term）：本次会话里的 `messages`——就是第 02 章的 `ChatSession`
2. 长期记忆（long-term）：跨会话、跨任务持续存在的「事实 / 偏好」——`FileMemory`
3. 向量记忆（semantic）：靠「语义相似」检索而非精确匹配——`VectorMemory`

并回答那个老题：**RAG 与 Memory 的边界**（见第 09 章正文第 3 节）。

设计原则延续：不改任何已有签名；向量记忆的嵌入函数通过参数注入，
默认用离线可跑的「玩具 2-gram 嵌入」作教具，真实项目换成 embedding 模型。
"""

from __future__ import annotations

import json
import os


# ---------- 长期记忆：文件 ----------

class FileMemory:
    """跨会话的长期记忆：一个 key→value 的事实库，落盘到 JSON 文件。

    什么时候用：记忆是「精确可定位」的——用户的名字、偏好、上一单的目标，
    用 key 精确读写即可。文件记忆适合「小而精确、需要跨会话」的东西。

    用法：
        mem = FileMemory("user_memory.json")
        mem.remember("user_name", "小明")
        mem.save()                       # 落盘，才算跨会话
        # —— 另一个会话 / 进程 ——
        mem2 = FileMemory("user_memory.json")
        mem2.recall("user_name")         # '小明'
    """

    def __init__(self, path: str = "memory.json"):
        self.path = path
        self._data: dict = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def remember(self, key: str, value) -> None:
        """记一条事实。注意：只改内存态，要跨会话得再 save()。"""
        self._data[key] = value

    def recall(self, key: str, default=None):
        """取一条事实；没有则返回 default。"""
        return self._data.get(key, default)

    def forget(self, key: str) -> None:
        self._data.pop(key, None)

    def facts(self) -> dict:
        """当前全部事实的浅拷贝。"""
        return dict(self._data)

    def save(self) -> None:
        """落盘到 JSON。落盘了才算「跨会话记忆」。"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        """从盘上重读（覆盖内存态）。"""
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self._data = json.load(f)


# ---------- 向量记忆：语义 ----------

def toy_embed(text: str) -> dict[str, float]:
    """玩具嵌入：字符 2-gram 词袋。**离线可跑，只为演示检索的机械结构。**

    用连续两个字符的出现次数做向量，靠「字符共现」判断表面相似——不是真语义。
    真实项目换成 embedding 模型（OpenAI / DeepSeek 的 text-embedding），把
    `VectorMemory(embed=...)` 传进去即可，检索流程不用改。
    """
    text = (text or "").strip()
    grams: dict[str, float] = {}
    if len(text) == 1:
        grams[text] = 1.0
        return grams
    for i in range(len(text) - 1):
        g = text[i:i + 2]
        grams[g] = grams.get(g, 0.0) + 1.0
    return grams


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """两个词袋向量的余弦相似度。"""
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class VectorMemory:
    """语义记忆：把句子编码成向量，按「相似度」检索而非精确匹配。

    什么时候用：记忆是「模糊的 / 按意思找的」——「用户上次问过退款政策吗？」
    这种没法用一个 key 精确查到的东西，就交给语义检索。

    用法：
        vmem = VectorMemory()               # 默认玩具嵌入；真实换成 embed=your_embed
        vmem.add("用户问过退款政策是怎样的")
        vmem.search("退钱怎么退", top_k=3)
    """

    def __init__(self, embed=None):
        self._embed = embed or toy_embed
        self._items: list[dict] = []

    def add(self, text: str, meta: dict | None = None) -> None:
        self._items.append({
            "text": text,
            "vec": self._embed(text),
            "meta": meta or {},
        })

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """返回 top_k 条最相似的记忆片段：[{score, text, meta}, ...]。"""
        qv = self._embed(query)
        scored = sorted(
            ((cosine(qv, it["vec"]), it) for it in self._items),
            key=lambda x: x[0],
            reverse=True,
        )
        return [
            {"score": round(s, 4), "text": it["text"], "meta": it["meta"]}
            for s, it in scored[:top_k]
        ]

    def __len__(self) -> int:
        return len(self._items)


def retrieved_context(memory: VectorMemory, query: str, top_k: int = 3) -> str:
    """RAG 的最小闭环：检索 → 把命中的片段拼成一段「上下文」，可塞进 prompt/session。

    - Memory 是「关于这次任务/这个用户的长期状态」，要持续写、主动注入；
    - RAG 是「按需检索外部知识」，只读、按 query 拉。
    本函数演示的是 RAG 的「检索 → 拼上下文」这一半，不是 Memory 的「写」。
    """
    hits = memory.search(query, top_k=top_k)
    if not hits:
        return ""
    lines = [f"- {h['text']}" for h in hits]
    return "以下是与你问题相关的记忆片段：\n" + "\n".join(lines)