"""LLMClient —— 统一的 LLM 调用客户端（Harness 内核，第 01 章落地）。

从 .env 读取 LLM_PROVIDER，自动选对应的 API Key / Base URL / 模型名。
换模型只改 .env，不改代码。对外返回 LLMResult，不漏 SDK 对象。

接口从第 01 章起冻住，后续章节只加能力（重试 / token 计数 / trace），
不改 chat() 签名。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterator

from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

# 找到仓库根目录的 .env（案例可在任意子目录运行）
load_dotenv(find_dotenv(usecwd=True))

# 提供商 → (API Key 环境变量, Base URL 环境变量, 模型名 环境变量)
# 换模型只改 .env 里的 LLM_PROVIDER，代码无需改动。
PROVIDERS = {
    "deepseek": ("DEEPSEEK_API_KEY",   "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"),
    "qwen":     ("DASHSCOPE_API_KEY",  "QWEN_BASE_URL",     "QWEN_MODEL"),
    "openai":   ("OPENAI_API_KEY",     "OPENAI_BASE_URL",   "OPENAI_MODEL"),
    "ollama":   ("OLLAMA_API_KEY",     "OLLAMA_BASE_URL",   "OLLAMA_MODEL"),
}


@dataclass
class LLMResult:
    """LLM 调用的统一返回结构。

    把 SDK 细节收在内核里，上层只认这个结构。
    - content: 模型回复的文本
    - tool_calls: 工具调用列表（第 05 章起用，第 01 章恒为空）
    - usage: token 用量（第 02 章起用）
    - raw: 原始 SDK 响应，调试用，上层尽量别碰
    """
    content: str = ""
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    raw: object = None


class LLMClient:
    """最小可用的 LLM 客户端封装。

    后续章节会在此基础上扩展：token 计数、重试、trace、结构化输出等，
    但 chat() / stream() 的签名保持不变。
    """

    def __init__(self, provider: str | None = None):
        provider = provider or os.getenv("LLM_PROVIDER", "deepseek")
        if provider not in PROVIDERS:
            raise ValueError(
                f"未知的 LLM_PROVIDER={provider!r}，可选: {list(PROVIDERS)}"
            )
        self.provider = provider
        key_env, url_env, model_env = PROVIDERS[provider]

        self.model = os.getenv(model_env)
        if not self.model:
            raise ValueError(f"环境变量 {model_env} 未设置，请检查 .env")

        # Ollama 本地不需要 API Key，给个占位值即可
        api_key = os.getenv(key_env) or "ollama"
        base_url = os.getenv(url_env)
        if not base_url:
            raise ValueError(f"环境变量 {url_env} 未设置，请检查 .env")

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages: list[dict], **kwargs) -> LLMResult:
        """同步调用，返回 LLMResult。

        Args:
            messages: OpenAI 消息格式，如 [{"role": "user", "content": "你好"}]
            **kwargs: 透传给底层 create，如 temperature、max_tokens 等。
        """
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False,
            **kwargs,
        )
        return self._to_result(resp)

    def stream(self, messages: list[dict], **kwargs) -> Iterator[str]:
        """流式调用，逐块 yield 出文本 delta。

        内部处理了首块 delta.content 为 None 的情况，上层只拿 str。
        """
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    def chat_text(self, user: str, system: str | None = None, **kwargs) -> str:
        """便捷方法：单轮问答，直接拿文本结果。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        return self.chat(messages, **kwargs).content

    @staticmethod
    def _to_result(resp) -> LLMResult:
        """把 SDK 响应收成 LLMResult。"""
        msg = resp.choices[0].message
        usage = {}
        if getattr(resp, "usage", None):
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }
        return LLMResult(
            content=msg.content or "",
            tool_calls=getattr(msg, "tool_calls", None) or [],
            usage=usage,
            raw=resp,
        )


if __name__ == "__main__":
    # 自检：确认配置能跑通
    llm = LLMClient()
    print(f"[配置] provider={llm.provider} model={llm.model}")
    result = llm.chat_text("用一个词回答：1+1=?")
    print(f"[模型回答] {result}")
