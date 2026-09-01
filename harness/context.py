"""context —— Context 治理（Harness 第六块砖，第 08 章落地）。

第 02 章埋下三根刺：上下文越聊越大（线性 token 成本）、越聊越贵、越聊越失焦
（lost in the middle，塞越多中段利用率越低）。第 02 章只给了「截断」这一刀，
第 08 章把它升级成治理工具箱，三招：

1. 压缩（compact / summarize）：用 LLM 把旧历史压成一段摘要，留语义、去废话
2. 取舍（select_by_budget）：按 token 预算挑「最有用的那次 tokens」进上下文
3. 按需读取（ReferenceLibrary）：会话里只放「目录」（短引用），需要时再拉全文

设计原则延续：这些都是「接收 messages → 返回新 messages」的纯函数，
不依赖 ChatSession、不改任何已有签名。压缩用的 LLM 通过参数传入，可在案例里替换。
"""

from __future__ import annotations


# ---------- 估算与基础 ----------

def estimate_tokens(messages: list[dict]) -> int:
    """粗略估算 token 数：中文按 1 字符 ≈ 1 token，其余按 4 字符 ≈ 1 token。

    教学用估算——工程上要接真实 tokenizer（tiktoken）或直接用 API 返回的 usage。
    这里的目的只是「相对大小」：判断哪段长、超没超预算，不需要绝对精确。
    """
    total = 0
    for m in messages:
        total += _token_cost(m)
    return total


def _token_cost(message: dict) -> int:
    text = message.get("content", "") or ""
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return cjk + max(0, (len(text) - cjk)) // 4


def keep_last_turns(messages: list[dict], turns: int) -> list[dict]:
    """保留 system + 最近 turns 个完整回合（不以 assistant 开头——按轮成对裁）。

    第 02 章 `truncate(keep_last_n)` 是按「条数」裁的，奇数条会从一轮中间切开、
    让历史以 assistant 开头。本函数按「轮」裁，根治这个问题。
    """
    system = [m for m in messages if m["role"] == "system"]
    rest = [m for m in messages if m["role"] != "system"]

    turns_list: list[list[dict]] = []
    cur: list[dict] = []
    for m in rest:
        if m["role"] == "user" and cur:      # 新的一轮开始
            turns_list.append(cur)
            cur = []
        cur.append(m)
    if cur:
        turns_list.append(cur)

    kept = [m for turn in turns_list[-turns:] for m in turn]
    return system + kept


# ---------- 压缩 ----------

def _render(messages: list[dict]) -> str:
    """把消息列表渲染成「role: content」的纯文本，供摘要器阅读。"""
    return "\n".join(f"{m['role']}: {m.get('content', '')}" for m in messages)


def summarize(llm, messages: list[dict], instruction: str | None = None) -> str:
    """用 LLM 把一段对话压成简洁摘要。

    关键点：摘要要保留「后续继续对话需要的东西」——人物 / 事实 / 已做的决定 /
    未完成事项，丢掉寒暄和重复。instruction 可覆盖默认的摘要指令。
    """
    system = instruction or (
        "你是对话压缩器。把下面的对话压缩成一段简洁摘要："
        "保留关键人物、事实、已做的决定、未完成事项；去掉寒暄、重复和过程废话。"
        "用第三人称、直接陈述，控制在几行以内，不要加任何引言或解释。"
    )
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": "请压缩以下对话：\n\n" + _render(messages)},
    ]
    return llm.chat(msgs).content


def compact(llm, messages: list[dict], keep_last_turns_n: int = 2,
            summary_instruction: str | None = None) -> list[dict]:
    """压缩版上下文：旧历史 → 一段摘要，最近 keep_last_turns_n 轮原样保留。

    返回结构：system（若有）+ 一条「【前文摘要】user 消息」+ 最近 N 轮原文。
    保留最近 N 轮原文，是因为「最近」往往承载着当前任务的直接脉络；
    更早的部分压缩成摘要，实现对 80% 的内容只付 5% 的 token。
    """
    system = [m for m in messages if m["role"] == "system"]
    rest = [m for m in messages if m["role"] != "system"]
    recent = keep_last_turns(rest, keep_last_turns_n)
    old = rest[: len(rest) - len(recent)]
    if not old:
        return list(messages)          # 没有旧历史可压，原样返回

    summary = summarize(llm, old, summary_instruction)
    return system + [{"role": "user", "content": f"【前文摘要】\n{summary}"}] + recent


# ---------- 取舍 ----------

def select_by_budget(messages: list[dict], max_tokens: int,
                     keep_system: bool = True) -> list[dict]:
    """按 token 预算取舍：从最新往旧塞，直到预算满；至少保留最新一条。

    「取舍」的朴素版：以「越新越相关」为相关性代理。真正的相关性打分
    （向量相似度 / 关键词）留给第 09 章记忆体系；这里先树起「预算」这个硬约束。
    """
    system = [m for m in messages if m["role"] == "system"] if keep_system else []
    rest = [m for m in messages if m["role"] != "system"]

    kept: list[dict] = []
    used = estimate_tokens(system)
    for m in reversed(rest):
        cost = _token_cost(m)
        if kept and used + cost > max_tokens:
            break                       # 预算满，停（但至少保留最新一条）
        kept.append(m)
        used += cost
    kept.reverse()

    while kept and kept[0]["role"] == "assistant":   # 按轮成对：别以 assistant 开头
        kept = kept[1:]
    return system + kept


# ---------- 按需读取 ----------

class ReferenceLibrary:
    """按需读取的最小实现：给长内容一个短目录，需要时再拉全文。

    思路：会话里不放原文，放「目录」（标题 + 一两句摘要，几 token）；
    模型需要详情时，用 fetch(ref) 把全文拉进来（或用工具让模型自己调）。
    这是第 09 章「记忆体系 / RAG」的预热——那时目录会变成可检索的索引。

        lib = ReferenceLibrary({"ref-1": "很长很长的原文……"})
        lib.catalog()         # 进上下文的是这个短目录
        lib.fetch("ref-1")    # 需要时再拉全文
    """

    def __init__(self, docs: dict[str, str] | None = None):
        self._docs = dict(docs or {})
        self._fetch_count = 0

    def catalog(self, max_snippet: int = 80) -> str:
        """返回「目录」：编号 + 每条文档的前几句（短）。这才是进上下文的东西。"""
        lines = []
        for ref, text in self._docs.items():
            snippet = text[:max_snippet].replace("\n", " ")
            lines.append(f"- {ref}：{snippet}")
        return "参考资料目录（需要详情时用 fetch 拉取）：\n" + "\n".join(lines)

    def fetch(self, ref: str) -> str:
        """按引用拉全文。真实场景这里可能接数据库 / API / 文件。"""
        self._fetch_count += 1
        if ref not in self._docs:
            raise KeyError(f"没有编号为 {ref!r} 的参考资料")
        return self._docs[ref]