"""ChatSession —— 带历史的聊天会话（Harness 第二块砖，第 02 章落地）。

职责（第 02 章只做这三件事，接口从此冻住）：
1. 攒消息历史（system / user / assistant）
2. 累积 token 用量
3. 提供最简单的截断治理（保留 system + 最近 N 条）

第 08 章会把「截断」升级成更聪明的 Context 治理（压缩 / 摘要 / 按需读取），
但那是在 truncate() 之上加新方法，不改本文件的公开签名。
"""

from __future__ import annotations

from harness.llm import LLMClient, LLMResult


class ChatSession:
    """多轮对话的最小状态容器。

    用法：
        session = ChatSession(system="你是一个简洁的助手")
        reply = session.ask("我叫小明")
        reply = session.ask("我叫什么？")   # 记得上文
        print(session.total_usage)          # 累积 token
        session.truncate(keep_last_n=6)     # 治理第一刀：截断
    """

    def __init__(self, llm: LLMClient | None = None, system: str | None = None):
        self.llm = llm or LLMClient()
        self.messages: list[dict] = []
        if system:
            self.messages.append({"role": "system", "content": system})
        self.total_usage: dict = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def ask(self, user: str, **kwargs) -> str:
        """问一轮：把 user 消息追加进历史 → 调模型 → 把回复追加回历史。

        返回模型回复文本。token 用量自动累积到 total_usage。
        """
        self.messages.append({"role": "user", "content": user})
        result: LLMResult = self.llm.chat(self.messages, **kwargs)
        self.messages.append({"role": "assistant", "content": result.content})
        self._accrue(result.usage)
        return result.content

    def truncate(self, keep_last_n: int = 6) -> None:
        """历史治理第一刀：保留 system + 最近 keep_last_n 条消息。

        为什么默认 6：一轮 = user + assistant 两条，6 条 ≈ 最近 3 轮。
        注意：截断会丢早期记忆（模型会「忘事」）——这是第 08 章
        Context 治理（压缩 / 摘要 / 按需读取）要解决的问题。

        （第 08 章加固）按轮成对裁：若最后片段从一轮中间切开、首条是
        assistant，就再往下丢到 user 为止，避免历史以 assistant 开头触发
        部分提供商的角色顺序报错。偶数 N 行为不变，奇数 N 更安全。
        """
        system = [m for m in self.messages if m["role"] == "system"]
        rest = [m for m in self.messages if m["role"] != "system"]
        kept = rest[-keep_last_n:]
        while kept and kept[0]["role"] not in ("user", "tool"):
            kept = kept[1:]
        self.messages = system + kept

    @property
    def turns(self) -> int:
        """已经问了几个用户回合。"""
        return sum(1 for m in self.messages if m["role"] == "user")

    def _accrue(self, usage: dict) -> None:
        for k in self.total_usage:
            self.total_usage[k] += usage.get(k, 0)
