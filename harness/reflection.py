"""reflection —— 失败策略与反思（Harness 第九块砖，第 11 章落地）。

第 06 章的容错（RetryPolicy / ResilientTool）是【傻重试】：同一个动作、
退避重来，只挡得住瞬时故障（超时 / 限流 / 网络抖动）。但动作本身错了呢？
重试一万次也没用。

第 11 章引入【反思式重试】：失败 → 把错误回喂给模型 → 让它思考
「为什么失败、该换什么」→ 换思路再试。这是 Self-Reflection：
和第 07 章「把解析错误回喂给模型自纠」同一招，只是粒度从『格式』
提升到『任务』。

这块砖提供：
1. `reflect`：把失败信息回喂，让模型给 verdict（继续 / 放弃）+ 原因 + 下一步
2. `retry_with_reflection`：执行 → 失败 → 反思 → 换思路 → 再试 的外层循环

原则：只加能力、不改 `AgentLoop.run`、不碰第 06 章的 `RetryPolicy`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from pydantic import BaseModel, Field

from harness.schema import structured_chat


class ReflectionModel(BaseModel):
    """让模型反思时输出的形状：继续还是放弃 + 原因 + 下一步。"""
    verdict: Literal["retry", "give_up"]
    reason: str = Field(..., description="为什么会失败，一两句")
    next_action: str = Field(..., description="若 retry，下一次该怎么改")


@dataclass
class Reflection:
    """一次反思的结论。"""
    verdict: str                              # retry / give_up
    reason: str = ""
    next_action: str = ""

    @classmethod
    def from_model(cls, m: ReflectionModel) -> "Reflection":
        return cls(m.verdict, m.reason, m.next_action)


def reflect(llm, goal: str, failure_log: str) -> Reflection:
    """把失败信息回喂给模型，让它反思：是换思路再试，还是承认做不了。

    复用第 07 章 structured_chat，输出 `{verdict, reason, next_action}` 这种
    程序能接住的结构，而不是一段「我觉得吧……」。llm 可换 FakeReflector。
    """
    system = (
        "你是一个会反思的执行器。给你一个任务、以及上一次尝试的失败信息，请判断："
        "是换个思路再试（verdict=retry，并在 next_action 里写清具体改法），"
        "还是承认做不了（verdict=give_up）。reason 用一两句说明为什么。"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"任务：{goal}\n\n上一次尝试的失败信息：\n{failure_log}"},
    ]
    return Reflection.from_model(structured_chat(llm, messages, ReflectionModel))


@dataclass
class ReflectionResult:
    """反思式重试的最终结果：成没成 + 每一轮都记了下来。"""
    goal: str
    success: bool = False
    result: str = ""
    attempts: list = field(default_factory=list)


def retry_with_reflection(llm, goal: str, attempt_fn: Callable[[str], str],
                          max_reflections: int = 2) -> ReflectionResult:
    """执行 → 失败 → 反思 → 换思路 → 再试；到反思上限或 verdict=give_up 即停。

    - attempt_fn(当前目标) -> str：成功返回结果字符串，失败抛异常。
    - 反思说 retry：用 `next_action` 替换目标，换思路再试（这才是「聪明重试」，
      区别于第 06 章同名动作的「傻重试」）。
    - 反思说 give_up、或反思次数用尽：停止，带上完整过程。
    """
    res = ReflectionResult(goal=goal)
    current = goal
    for attempt in range(max_reflections + 1):
        try:
            out = attempt_fn(current)
            res.success = True
            res.result = out
            res.attempts.append({"attempt": attempt + 1, "goal": current,
                                "outcome": "success", "result": out})
            return res
        except Exception as e:  # noqa: BLE001
            err = str(e)
            if attempt >= max_reflections:
                res.attempts.append({"attempt": attempt + 1, "goal": current,
                                    "outcome": "failed", "error": err})
                break                       # 反思次数用尽
            r = reflect(llm, goal, f"第 {attempt + 1} 次尝试（目标：{current}）失败：{err}")
            res.attempts.append({"attempt": attempt + 1, "goal": current,
                                "outcome": "failed", "error": err,
                                "verdict": r.verdict, "reason": r.reason})
            if r.verdict == "give_up":
                break                       # 模型承认做不了
            current = r.next_action or current
    return res