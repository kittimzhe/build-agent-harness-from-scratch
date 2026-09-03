"""harness —— 一个会生长的 Agent Runtime 内核。

本包随教程章节逐步演进：
- 第 01 章：LLMClient（llm.py）
- 第 02 章：ChatSession（session.py，消息状态与用量）
- 第 05 章：Tool / AgentLoop（loop.py，工具循环与护栏）
- 第 06 章：ToolError / RetryPolicy / ResilientTool / ToolRegistry（tools.py，重试 / 超时 / 幂等）
- 第 07 章：extract_json / strict_validate / structured_chat（schema.py，结构化输出与自纠）
- 第 08 章：estimate_tokens / keep_last_turns / summarize / compact / select_by_budget / ReferenceLibrary（context.py，Context 治理）
- 第 09 章：FileMemory / VectorMemory / toy_embed / cosine / retrieved_context（memory.py，记忆体系）
- 第 10 章：Plan / PlanStep / make_plan / execute_plan（planning.py，任务拆解与 Planning）
- 第 11 章：Reflection / reflect / retry_with_reflection（reflection.py，失败策略与反思）
- 第 12 章：plan_to_dict / plan_from_dict / save_checkpoint / load_checkpoint / run_plan_with_checkpoint（state.py，Checkpoint 与状态恢复）
- 第 13 章：AgentState / RuntimeEvent / MiniAgent（runtime.py，封装 Mini Agent Runtime）
- 第 14 章：TraceEvent / Trace / Tracer / ScriptedLLM（trace.py，可观测 log/metric/trace/replay）
- 第 15 章：StopConditions / ToolPolicy / PolicyGuard / DenySandbox / detect_injection（safety.py，终止条件·权限·安全）

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
from harness.memory import FileMemory, VectorMemory, toy_embed, cosine, retrieved_context
from harness.planning import Plan, PlanStep, make_plan, execute_plan
from harness.reflection import Reflection, ReflectionResult, reflect, retry_with_reflection
from harness.state import (
    plan_to_dict, plan_from_dict, save_checkpoint, load_checkpoint, run_plan_with_checkpoint,
)
from harness.runtime import AgentState, RuntimeEvent, MiniAgent
from harness.trace import TraceEvent, Trace, Tracer, ScriptedLLM
from harness.safety import (
    StopConditions, ToolPolicy, PolicyGuard, DenySandbox, InjectionReport, detect_injection,
)

__all__ = [
    "LLMClient", "LLMResult", "ChatSession",
    "Tool", "AgentLoop",
    "ToolError", "RetryPolicy", "ResilientTool", "ToolRegistry",
    "StructuredOutputError", "extract_json", "strict_validate", "structured_chat",
    "estimate_tokens", "keep_last_turns", "summarize", "compact",
    "select_by_budget", "ReferenceLibrary",
    "FileMemory", "VectorMemory", "toy_embed", "cosine", "retrieved_context",
    "Plan", "PlanStep", "make_plan", "execute_plan",
    "Reflection", "ReflectionResult", "reflect", "retry_with_reflection",
    "plan_to_dict", "plan_from_dict", "save_checkpoint", "load_checkpoint",
    "run_plan_with_checkpoint",
    "AgentState", "RuntimeEvent", "MiniAgent",
    "TraceEvent", "Trace", "Tracer", "ScriptedLLM",
    "StopConditions", "ToolPolicy", "PolicyGuard", "DenySandbox",
    "InjectionReport", "detect_injection",
]
