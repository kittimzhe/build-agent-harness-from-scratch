"""
llm_client.py —— 统一的 LLM 调用客户端（Harness 第一块砖）

从 .env 读取 LLM_PROVIDER，自动选对应的 API Key / Base URL / 模型名。
换模型只改 .env，不改代码。后面所有章节都会复用这个客户端。

用法：
    from llm_client import LLMClient
    llm = LLMClient()
    resp = llm.chat([{"role": "user", "content": "你好"}])
    print(resp.choices[0].message.content)
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 提供商 → (API Key 环境变量, Base URL 环境变量, 模型名 环境变量)
# 换模型只改 .env 里的 LLM_PROVIDER，代码无需改动。
PROVIDERS = {
    "deepseek": ("DEEPSEEK_API_KEY",   "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"),
    "qwen":     ("DASHSCOPE_API_KEY",  "QWEN_BASE_URL",     "QWEN_MODEL"),
    "openai":   ("OPENAI_API_KEY",     "OPENAI_BASE_URL",   "OPENAI_MODEL"),
    "ollama":   ("OLLAMA_API_KEY",     "OLLAMA_BASE_URL",   "OLLAMA_MODEL"),
}


class LLMClient:
    """最小可用的 LLM 客户端封装。

    后续章节会在此基础上扩展：token 计数、重试、trace、结构化输出等。
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

    def chat(self, messages: list[dict], stream: bool = False, **kwargs):
        """统一调用入口。

        Args:
            messages: OpenAI 消息格式，如 [{"role": "user", "content": "你好"}]
            stream: 是否流式输出。流式时返回迭代器，否则返回完整响应。
            **kwargs: 透传给底层 create，如 temperature、max_tokens 等。
        """
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            **kwargs,
        )

    def chat_text(self, user: str, system: str | None = None, **kwargs) -> str:
        """便捷方法：单轮问答，直接拿文本结果。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        resp = self.chat(messages, **kwargs)
        return resp.choices[0].message.content


if __name__ == "__main__":
    # 自检：确认配置能跑通
    llm = LLMClient()
    print(f"[配置] provider={llm.provider} model={llm.model}")
    answer = llm.chat_text("用一个词回答：1+1=?")
    print(f"[模型回答] {answer}")
