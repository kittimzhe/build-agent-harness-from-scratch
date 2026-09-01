"""tools —— 工具集合与容错（Harness 第四块砖，第 06 章落地）。

第 05 章的 AgentLoop 会在工具失败时把错误文本回喂给模型、让模型自己重试。
「模型重试」很贵：每轮重发全部历史 + 重新生成 token。第 06 章回答更工程的问题：

1. 重试（retry）：瞬时错误在【工具边界】内重试，模型根本看不见 → 省 token
2. 超时（timeout）：卡死的工具不能拖垮整个循环
3. 幂等（idempotency）：重试只在安全时做；非幂等工具靠幂等键去重

设计原则延续前几章：`AgentLoop.run()` 签名不动。容错做在「工具这层」——
`ResilientTool` 包在 `Tool` 外面，`AgentLoop` 调 `.run()` 时自动受益，零改动。
第 07 章会讲 schema 设计强化；第 15 章讲权限（审批）是在这里之上再包一层。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass

from harness.loop import Tool


class ToolError(Exception):
    """工具执行/容错层的统一错误。消息对模型友好，会经 AgentLoop 回喂。"""


@dataclass
class RetryPolicy:
    """工具的容错策略。

    - max_retries: 失败后最多再试几次（0 = 不重试，即第 05 章行为）
    - base_delay / delay_multiplier: 指数退避延迟（0.5s → 1s → 2s ...）
    - timeout: 单次调用超时秒数；None = 不超时
    - idempotent: 工具是否幂等（重试是否安全）。False 且有重试时，本层拒绝自动重试。
    """
    max_retries: int = 0
    base_delay: float = 0.5
    delay_multiplier: float = 2.0
    timeout: float | None = None
    idempotent: bool = False


def _call_with_timeout(func, args: dict, name: str, timeout: float | None):
    """在超时预算内执行一次工具调用。"""
    if timeout is None:
        return func(**args)
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(func, **args)
        try:
            return fut.result(timeout=timeout)
        except FutureTimeoutError:
            raise ToolError(
                f"工具 {name!r} 超时（超过 {timeout}s）。原线程可能仍在后台运行——"
                f"生产环境要配合取消机制，这里先保证循环不被卡死。"
            ) from None


def run_with_policy(func, args: dict, name: str,
                    policy: RetryPolicy | None = None) -> str:
    """执行工具并应用容错策略。返回 str 结果；重试耗尽仍失败则抛 ToolError。"""
    policy = policy or RetryPolicy()
    attempt = 0
    delay = policy.base_delay
    while True:
        try:
            return str(_call_with_timeout(func, args, name, policy.timeout))
        except ToolError as e:
            # 工具级错误（如超时）：信息已成型，直接透传；非幂等时额外注明「未重试」。
            if attempt < policy.max_retries and policy.idempotent:
                attempt += 1
                time.sleep(delay)
                delay *= policy.delay_multiplier
                continue
            if policy.max_retries > 0 and not policy.idempotent:
                raise ToolError(f"{e}（该工具标记为非幂等，未自动重试）") from e
            raise
        except Exception as e:  # noqa: BLE001 —— 工具内部未声明的异常统一收口
            # 关键门槛：只有在工具幂等时才自动重试。
            # 非幂等工具（下单/扣款）盲目重试 = 重复副作用，宁可不重试、把错误交出去。
            if attempt < policy.max_retries and policy.idempotent:
                attempt += 1
                time.sleep(delay)
                delay *= policy.delay_multiplier
                continue
            note = "（已重试 %d 次）" % attempt
            if policy.max_retries > 0 and not policy.idempotent:
                note = "；该工具标记为非幂等，未自动重试（避免重复副作用）"
            raise ToolError(f"工具 {name!r} 执行失败{note}：{e}") from e


class ResilientTool(Tool):
    """带容错策略的 Tool：重试 / 超时 / 幂等，包在 Tool 外面。

    AgentLoop 调 `.run()` 时自动继承容错，无需改循环代码。
    """

    def __init__(self, func, name=None, description=None, parameters=None,
                 policy: RetryPolicy | None = None):
        super().__init__(func, name=name, description=description, parameters=parameters)
        self.policy = policy or RetryPolicy()

    def run(self, **kwargs):
        return run_with_policy(self.func, kwargs, self.name, self.policy)


class ToolRegistry:
    """工具注册表：统一管理工具集合 + 每条工具的策略 + 幂等键去重。

    适合「工具很多、需要集中治理」的场景；也给第 15 章的权限审批留好插口。
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._policies: dict[str, RetryPolicy] = {}
        self._results: dict[str, str] = {}  # idempotency_key -> 上次结果

    def register(self, tool: Tool, policy: RetryPolicy | None = None) -> None:
        self._tools[tool.name] = tool
        self._policies[tool.name] = policy or RetryPolicy()

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def run(self, name: str, args: dict | None = None,
            idempotency_key: str | None = None) -> str:
        """按注册的容错策略执行工具。给 idempotency_key 时同键去重（返回缓存结果）。"""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"没有叫 {name!r} 的工具，可选：{self.names()}")
        if idempotency_key and idempotency_key in self._results:
            return self._results[idempotency_key]
        result = run_with_policy(tool.func, args or {}, name, self._policies[name])
        if idempotency_key:
            self._results[idempotency_key] = result
        return result