"""AgentLoop —— 最小的工具循环（Harness 第三块砖，第 05 章落地）。

「从聊天到行动」的核心：让模型在循环里自主决定
    Thought（想）→ Action（调工具）→ Observation（看结果）→ ... → Final（答）

职责（第 05 章只做这三件事，接口从此冻住）：
1. 把 Python 函数包装成模型可调用的 Tool（name + description + 参数 schema）
2. 跑循环：模型要工具就执行、把结果塞回消息列表、再问模型，直到给出最终回答
3. 护栏：max_rounds 最大轮数，防止死循环烧钱

第 06 章会加工具容错（重试 / 超时 / 幂等），第 15 章会加权限审批——
都是在 run() 之上加能力，不改本文件的公开签名。
"""

from __future__ import annotations

import json

from harness.llm import LLMClient, LLMResult


class Tool:
    """把一个普通 Python 函数包装成模型可调用的工具。

    用法：
        def add(a: float, b: float) -> float:
            \"\"\"两数相加\"\"\"
            return a + b

        tool = Tool(add, parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"}, "b": {"type": "number"},
            },
            "required": ["a", "b"],
        })
    """

    def __init__(self, func, name: str | None = None,
                 description: str | None = None, parameters: dict | None = None):
        self.func = func
        self.name = name or func.__name__
        self.description = description or (func.__doc__ or "").strip()
        # parameters 是 JSON Schema；怎么设计好它，第 04 章展开
        self.parameters = parameters or {"type": "object", "properties": {}}

    def schema(self) -> dict:
        """给模型看的工具说明书（OpenAI Function Calling 格式）。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, **kwargs):
        """真正执行。参数解析失败 / 执行异常由 AgentLoop 捕获并回喂给模型。"""
        return self.func(**kwargs)


class AgentLoop:
    """最小工具循环：要工具就给工具，直到模型给出最终回答或撞上护栏。

    用法：
        loop = AgentLoop(tools=[Tool(get_time), Tool(add)], max_rounds=8)
        out = loop.run("现在几点？再加一下 1 和 2")
        print(out["reply"], out["rounds"])
    """

    def __init__(self, llm: LLMClient | None = None,
                 tools: list[Tool] | None = None, max_rounds: int = 8):
        self.llm = llm or LLMClient()
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.max_rounds = max_rounds

    def run(self, user_input: str, system: str | None = None) -> dict:
        """跑一次任务，返回 {reply, rounds, messages, stopped_by}。

        stopped_by: "model"（模型自然给出最终回答）或 "max_rounds"（撞护栏被硬停）。
        """
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_input})

        for round_no in range(1, self.max_rounds + 1):
            result: LLMResult = self.llm.chat(
                messages,
                tools=[t.schema() for t in self.tools.values()],
            )

            # 终止条件①：模型不再要工具 —— 循环自然结束
            if not result.tool_calls:
                messages.append({"role": "assistant", "content": result.content})
                return {
                    "reply": result.content,
                    "rounds": round_no,
                    "messages": messages,
                    "stopped_by": "model",
                }

            # 模型要工具：把 assistant 的 tool_calls 原样记进历史
            messages.append({
                "role": "assistant",
                "content": result.content or None,
                "tool_calls": result.tool_calls,
            })

            # 逐个执行工具，把结果以 role="tool" 塞回历史（Observation）
            for tc in result.tool_calls:
                messages.append(self._execute(tc))

        # 终止条件②：超过最大轮数 —— 护栏硬停（防死循环烧钱）
        return {
            "reply": f"（已达到最大轮数 {self.max_rounds}，循环被护栏终止）",
            "rounds": self.max_rounds,
            "messages": messages,
            "stopped_by": "max_rounds",
        }

    def _execute(self, tc: dict) -> dict:
        """执行单个工具调用，返回 role="tool" 的消息。

        任何失败（参数解析 / 工具不存在 / 执行异常）都捕获并作为
        观察结果回喂给模型，让它自己纠错——而不是让循环崩掉。
        """
        name = tc["function"]["name"]
        try:
            args = json.loads(tc["function"]["arguments"] or "{}")
        except json.JSONDecodeError as e:
            output = f"工具参数不是合法 JSON：{e}"
        else:
            tool = self.tools.get(name)
            if tool is None:
                output = f"没有叫 {name!r} 的工具，可选：{list(self.tools)}"
            else:
                try:
                    output = str(tool.run(**args))
                except Exception as e:  # noqa: BLE001 —— 工具异常要回喂模型
                    output = f"工具执行出错：{e}"
        return {
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": output,
        }
