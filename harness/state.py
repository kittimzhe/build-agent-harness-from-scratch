"""state —— Checkpoint 与状态恢复（Harness 第十块砖，第 12 章落地）。

第 10 章的 `Plan` 有天然的状态（step 的 done/failed），第 11 章的反思有轨迹
（ReflectionResult.attempts）——但都在内存里，进程一崩全丢。第 12 章把状态
序列化落盘，做到断点续跑，思路对齐 **Durable Execution**：

- 状态是唯一事实（SSOT）：执行只是「推进状态 + 每一步立刻落盘」。
- 进程崩溃不可怕：从盘上读回状态，接着做，重跑一切「还没 done」的步骤。
- SAVE 是常态、不是事后：先落盘再继续，崩了才不丢。

这块砖提供：
1. `plan_to_dict` / `plan_from_dict`：Plan ↔ 可 JSON 序列化的 dict
2. `save_checkpoint` / `load_checkpoint`：落盘与恢复
3. `run_plan_with_checkpoint`：每步执行前后都存盘；失败落盘后停止，可随时恢复

设计原则：只加能力、不改 `Plan` / `execute_plan` 的既有签名。
"""

from __future__ import annotations

import json
from typing import Callable

from harness.planning import Plan, PlanStep

CHECKPOINT_VERSION = 1


def plan_to_dict(plan: Plan) -> dict:
    """Plan → 可 JSON 序列化的 dict（这就是「状态序列化」）。"""
    return {
        "version": CHECKPOINT_VERSION,
        "goal": plan.goal,
        "steps": [
            {"description": s.description, "status": s.status, "result": s.result}
            for s in plan.steps
        ],
    }


def plan_from_dict(data: dict) -> Plan:
    """dict → Plan（反序列化）。"""
    steps = [
        PlanStep(d["description"], d.get("status", "pending"), d.get("result", ""))
        for d in data.get("steps", [])
    ]
    return Plan(goal=data.get("goal", ""), steps=steps)


def save_checkpoint(plan: Plan, path: str = "checkpoint.json") -> None:
    """把计划当前状态落盘。落盘了，进程崩/被杀都能从这恢复。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan_to_dict(plan), f, ensure_ascii=False, indent=2)


def load_checkpoint(path: str = "checkpoint.json") -> Plan:
    """从盘上读回计划状态。"""
    with open(path, encoding="utf-8") as f:
        return plan_from_dict(json.load(f))


def run_plan_with_checkpoint(plan: Plan, executor: Callable[[str, int], str],
                             path: str = "checkpoint.json") -> Plan:
    """带 checkpoint 地执行计划：只跑「还没 done」的步骤，每步前后都落盘。

    - 只跳过 status == done 的步骤；pending / in_progress / failed 都会重跑
      （at-least-once：失败的那步在恢复时会被重新执行）。
    - 每个步骤：先置 in_progress 并落盘（崩溃后恢复时知道卡在哪），再执行；
      成功置 done、失败置 failed 并落盘后把异常抛出去（停止本次执行）。
    - 与第 10 章 execute_plan 的不同：（a）每步都持久化；（b）failed 不被永久
      跳过，恢复时会重跑——因为「没 done 就是没做完」。
    """
    for i, step in enumerate(plan.steps):
        if step.status == "done":
            continue
        step.status = "in_progress"
        save_checkpoint(plan, path)
        try:
            step.result = executor(step.description, i)
            step.status = "done"
        except Exception as e:  # noqa: BLE001
            step.status = "failed"
            step.result = str(e)
            save_checkpoint(plan, path)
            raise                       # 本次执行到此为止，但进度已落盘，可恢复
        save_checkpoint(plan, path)
    return plan