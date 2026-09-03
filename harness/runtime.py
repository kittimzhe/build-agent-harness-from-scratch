"""runtime —— 封装 Mini Agent Runtime（Harness 第十一块砖，第 13 章落地）。

前面十块砖（llm / session / loop / tools / schema / context / memory / planning /
reflection / state）各管一块，但每块都得手动装配。第 13 章把它们封装成一个
可复用的 mini runtime：一个 Agent 实例 = 一段状态机 + 一段事件循环 + 可插拔钩子。

- 状态机：new → running → done | error；reset() 回到 new 可复用。
- 事件循环：「一次 run = 一圈状态机」，内部委托 AgentLoop（第 05 章）去和模型过招。
- 钩子：on_event 让上层能观察每一步——第 14 章的 trace 就是这种钩子的系统化。

对比：LangGraph 把状态流转显式成语义图；本 mini runtime 是「一条循环 + 显式状态
字段」。两者核心价值观一致：显式状态、可插拔、可观察。mini runtime 更薄，
足够承载本教程主线，也正好让你看清「框架在替你做什么」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from harness.llm import LLMClient, LLMResult
from harness.loop import AgentLoop, Tool


class AgentState:
    """Agent 的状态机：一次 run 走 new → running → done/error。"""
    NEW = "new"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# 合法迁移表：显式写出，非法迁移直接抛错（状态机里的护栏）
_TRANSITIONS = {
    AgentState.NEW: {AgentState.RUNNING},
    AgentState.RUNNING: {AgentState.DONE, AgentState.ERROR},
}


@dataclass
class RuntimeEvent:
    """一次运行中发出的事件（第 14 章 trace 的原料）。"""
    type: str                       # start / finish / error
    payload: dict = field(default_factory=dict)


class MiniAgent:
    """一个可复用的 mini Agent runtime。

    用法：
        agent = MiniAgent(system="你是周报助手", tools=[Tool(add)], name="reporter")
        agent.on(lambda e: print(e.type))   # 钩子：观察每一步
        out = agent.run("算一下 1+2")        # new → running → done/error
        print(agent.state, agent.events)     # 状态与全程事件都可取到
    """

    def __init__(self, llm: LLMClient | None = None, system: str | None = None,
                 tools: list[Tool] | None = None, max_rounds: int = 8,
                 name: str = "agent", on_event: Callable[[RuntimeEvent], None] | None = None):
        self.llm = llm or LLMClient()
        self.name = name
        self.system = system
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.max_rounds = max_rounds
        self.hooks: list[Callable[[RuntimeEvent], None]] = [on_event] if on_event else []
        self.state = AgentState.NEW
        self.events: list[RuntimeEvent] = []

    # ---- 钩子 ----
    def on(self, hook: Callable[[RuntimeEvent], None]) -> "MiniAgent":
        self.hooks.append(hook)
        return self

    def _emit(self, etype: str, **payload) -> None:
        ev = RuntimeEvent(etype, payload)
        self.events.append(ev)
        for h in self.hooks:
            h(ev)

    # ---- 状态机 ----
    def _transition(self, to: str) -> None:
        if to not in _TRANSITIONS.get(self.state, set()):
            raise RuntimeError(f"非法状态迁移：{self.state} -> {to}")
        self.state = to

    def reset(self) -> "MiniAgent":
        """清空本次运行，回到 new，可复用作下一次任务。"""
        self.state = AgentState.NEW
        self.events = []
        return self

    # ---- 事件循环 ----
    def run(self, user_input: str, system: str | None = None) -> dict:
        """跑一次任务：new → running → done | error。返回 {reply, rounds, state, ...}。"""
        if self.state != AgentState.NEW:
            raise RuntimeError(f"Agent 不是 new 状态（当前 {self.state}），先 reset() 再跑下一单")
        self._transition(AgentState.RUNNING)
        self._emit("start", input=user_input)

        loop = AgentLoop(llm=self.llm, tools=list(self.tools.values()), max_rounds=self.max_rounds)
        try:
            out = loop.run(user_input, system or self.system)
        except Exception as e:  # noqa: BLE001 —— 任何崩都不该穿出 runtime，记成 error 事件
            self._transition(AgentState.ERROR)
            self._emit("error", error=str(e))
            return {"reply": "", "error": str(e), "state": self.state}

        if out["stopped_by"] == "model":
            self._transition(AgentState.DONE)
            self._emit("finish", reply=out["reply"], rounds=out["rounds"])
        else:  # max_rounds 护栏硬停
            self._transition(AgentState.ERROR)
            self._emit("error", error=f"护栏终止（stopped_by={out['stopped_by']}）",
                       rounds=out["rounds"])
        return {**out, "state": self.state}