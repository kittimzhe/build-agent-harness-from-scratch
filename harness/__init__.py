"""harness —— 一个会生长的 Agent Runtime 内核。

本包随教程章节逐步演进：
- 第 01 章：LLMClient（llm.py）
- 第 02 章：ChatSession（session.py，消息状态与用量）
- 第 05 章：Tool / AgentLoop（loop.py，工具循环与护栏）
- 第 06 章：ToolError / RetryPolicy / ResilientTool / ToolRegistry（tools.py，重试 / 超时 / 幂等）
- 第 07 章：extract_json / strict_validate / structured_chat（schema.py，结构化输出与自纠）
- 第 08 章：estimate_tokens / keep_last_turns / summarize / compact / select_by_budget / ReferenceLibrary（context.py，Context 治理）
- 第 12 章：state（Checkpoint / 状态恢复）
- 第 14 章：trace（日志 / 回放）

设计原则：
1. 内核只加能力，不改已公开接口。`LLMClient.chat` / `ChatSession.ask` /
   `AgentLoop.run` 的签名从各自章节起冻住。
2. 对外返回自己的结构（LLMResult / 纯 dict），不漏 OpenAI SDK 对象进上层。
3. 配置用 find_dotenv 自动查找，案例可在任意子目录运行。
"""

from harness.llm import LLMClient, LLMResult
from harness.session import ChatSession
from harness.loop import Tool, AgentLoop
from harness.tools import ToolError, RetryPolicy, ResilientTool, ToolRegistry
from harness.schema import StructuredOutputError, extract_json, strict_validate, structured_chat
from harness.context import (
    estimate_tokens, keep_last_turns, summarize, compact, select_by_budget, ReferenceLibrary,
)

__all__ = [
    "LLMClient", "LLMResult", "ChatSession",
    "Tool", "AgentLoop",
    "ToolError", "RetryPolicy", "ResilientTool", "ToolRegistry",
    "StructuredOutputError", "extract_json", "strict_validate", "structured_chat",
    "estimate_tokens", "keep_last_turns", "summarize", "compact",
    "select_by_budget", "ReferenceLibrary",
]
