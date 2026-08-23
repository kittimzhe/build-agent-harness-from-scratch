"""harness —— 一个会生长的 Agent Runtime 内核。

本包随教程章节逐步演进：
- 第 01 章：LLMClient（本文件）
- 第 05 章：loop（ReAct 循环）
- 第 06 章：tools（工具集合）
- 第 12 章：state（Checkpoint / 状态恢复）
- 第 14 章：trace（日志 / 回放）

设计原则：
1. 内核只加能力，不改已公开接口。`LLMClient.chat` 的签名从第 01 章起冻住。
2. 对外返回自己的结构（LLMResult），不漏 OpenAI SDK 对象进上层。
3. 配置用 find_dotenv 自动查找，案例可在任意子目录运行。
"""

from harness.llm import LLMClient, LLMResult

__all__ = ["LLMClient", "LLMResult"]
