"""planning —— 任务拆解与 Planning（Harness 第八块砖，第 10 章落地）。

第 05 章的 `AgentLoop` 是 **ReAct**：边想边做、模型每轮只决定「下一步」，
没有全局计划。第 10 章引入 **Plan-and-Execute**：先让模型把大目标拆成
一份步骤清单，再逐步执行、逐条打钩。

两种范式不是替代关系，是取舍（见正文第 2 节）。这块砖提供：
1. `make_plan`：复用第 07 章的结构化输出（structured_chat），让 LLM 吐出一份步骤清单
2. `Plan` / `PlanStep`：把「计划」变成可推进、可观察状态的对象
3. `execute_plan`：逐步执行，每步结果串起来；失败即停（第 11 章再谈失败策略）

设计原则：只加能力、不改 `AgentLoop.run` / `ChatSession.ask` / `LLMClient.chat`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, Field

from harness.schema import structured_chat


class PlanModel(BaseModel):
    """让模型输出的计划形状：一个按执行顺序排列的步骤清单。"""
    steps: list[str] = Field(..., description="按执行顺序排列的步骤清单，每步一句话")


@dataclass
class PlanStep:
    """计划里的一步。status：pending / in_progress / done / failed"""
    description: str
    status: str = "pending"
    result: str = ""


class Plan:
    """一份可推进的计划：步骤清单 + 前进指针 + 可观察进度。

    status 状态机：pending → in_progress → done | failed
    与第 05 章 AgentLoop 的「模型每轮现想下一步」不同，Plan 把「做什么」
    先固化下来，执行只负责「推进 + 打钩」。
    """

    def __init__(self, steps, goal: str = ""):
        self.goal = goal
        self.steps = [PlanStep(s) if isinstance(s, str) else s for s in steps]

    # 容器协议，方便遍历
    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self):
        return iter(self.steps)

    def __getitem__(self, i: int) -> PlanStep:
        return self.steps[i]

    def next_action(self) -> PlanStep | None:
        """第一个未完成（pending / in_progress）的步骤——执行指针。"""
        for s in self.steps:
            if s.status in ("pending", "in_progress"):
                return s
        return None

    def mark_done(self, index: int, result: str = "") -> None:
        self.steps[index].status = "done"
        self.steps[index].result = result

    def mark_failed(self, index: int, result: str = "") -> None:
        self.steps[index].status = "failed"
        self.steps[index].result = result

    def is_complete(self) -> bool:
        return all(s.status == "done" for s in self.steps)

    def progress(self) -> str:
        """可读进度：[x] 完成 / [!] 失败 / [ ] 未做。"""
        lines = []
        for s in self.steps:
            mark = "x" if s.status == "done" else "!" if s.status == "failed" else " "
            lines.append(f"[{mark}] {s.description}")
        return "\n".join(lines)


def make_plan(llm, goal: str, max_steps: int = 5, hint: str = "") -> Plan:
    """让 LLM 把目标拆成一份步骤清单（Plan-and-Execute 的「Plan」这半）。

    复用第 07 章 structured_chat：要求模型输出 `{"steps": [...]}` 这种结构，
    解析失败自动自纠。FakeLLM 可注入，测试无需 API。
    """
    instruction = (
        "把下面的目标拆成一份可执行的步骤清单，"
        f"最多 {max_steps} 步，按执行顺序排列。"
        "每步用一句话、要具体可执行、能判断「做没做完」。"
    )
    if hint:
        instruction += f"\n{hint}"
    messages = [
        {"role": "system", "content": "你是任务规划器。" + instruction},
        {"role": "user", "content": f"目标：{goal}"},
    ]
    spec = structured_chat(llm, messages, PlanModel)
    return Plan(steps=spec.steps, goal=goal)


def execute_plan(plan: Plan, executor: Callable[[str, int], str]) -> list[dict]:
    """逐步执行计划：executor(步骤描述, 序号) -> 结果字符串。

    - 每步先置 in_progress，成功置 done、失败置 failed 并立即停止。
    - 「失败即停」是有意为之：Plan-and-Execute 遇到计划中断不该硬往下跑，
      该怎么补偿（重试 / 反思 / 重规划）留给第 11 章。
    """
    results: list[dict] = []
    for i, step in enumerate(plan.steps):
        if step.status in ("done", "failed"):
            continue
        step.status = "in_progress"
        try:
            out = executor(step.description, i)
            step.status = "done"
            step.result = out
            results.append({"index": i, "step": step.description, "status": "done", "result": out})
        except Exception as e:  # noqa: BLE001 —— 失败即停，第 11 章再谈补偿
            step.status = "failed"
            step.result = str(e)
            results.append({"index": i, "step": step.description, "status": "failed", "result": str(e)})
            break
    return results