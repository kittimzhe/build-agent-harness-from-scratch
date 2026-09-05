"""safety —— 终止条件 · 权限 · 安全（Harness 第十三块砖，第 15 章落地）。

生产级 Agent 飞不出这三件事：该停的时候停得住（终止条件）、不该碰的碰不了
（最小授权 + 审批）、坏东西跑不出圈（sandbox）+ 不被 prompt 注入带偏。

- StopConditions：终止条件统一检查（max_rounds / 输出预算 / 停止短语）
- ToolPolicy + PolicyGuard：最小授权（read < write < execute）+ 敏感工具人工审批
- DenySandbox：危险操作黑名单（让「删库/读密码/起子进程」这类调用被拦下）
- detect_injection / InjectionReport：提示注入的启发式检测

设计原则：和上一章一样——安全**走包装、不走侵入**。PolicyGuard 把工具包起来，
MiniAgent / AgentLoop 照旧 `.run()`，什么循环代码都不用改。包装可叠加：
(ResilientTool → GuardedTool) 就是「先容错、再鉴权」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from harness.loop import Tool
from harness.tools import ToolError

# read < write < execute：权限有高低，最小授权只给够用的
PERMISSION_ORDER = {"read": 1, "write": 2, "execute": 3}


def has_permission(granted: str, required: str) -> bool:
    """granted 是否覆盖 required。"""
    return PERMISSION_ORDER.get(granted, 0) >= PERMISSION_ORDER.get(required, 0)


@dataclass
class StopConditions:
    """终止条件：把「该不该停」统一成一个检查器。

    AgentLoop 里的 max_rounds 是其中一条（撞护栏硬停）；这里再补两条：
    输出预算（别让模型喷出巨量文本）和停止短语（命中文案即停，如「任务完成」）。
    """
    max_rounds: int = 8
    max_output_chars: int | None = None
    stop_phrases: tuple = ()

    def check(self, rounds: int, output_text: str = "") -> str | None:
        """要停返回原因，不停返回 None。"""
        if rounds >= self.max_rounds:
            return f"超过 max_rounds={self.max_rounds}"
        if self.max_output_chars is not None and len(output_text) > self.max_output_chars:
            return f"输出超过 {self.max_output_chars} 字符"
        for p in self.stop_phrases:
            if p in output_text:
                return f"命中停止短语 {p!r}"
        return None


@dataclass
class ToolPolicy:
    """一条工具的安全要求：需要什么权限、要不要人工审批。"""
    level: str = "read"             # read / write / execute
    needs_approval: bool = False


class DenySandbox:
    """危险操作黑名单：命中即拒。真正的 sandbox 应做系统级隔离（子进程/容器），
    这里先立住「在最外层拦一道」的语义——黑名单拦得住图省事的坏调用。

    可自定义 deny，默认拦：删东西 / 关机 / 读密码 / 起子进程 / 直连网络等。
    """
    DEFAULT_DENY = ("rm -rf", "shutdown", "curl", "wget", "import os",
                    "subprocess", "/etc/passwd", "open(")

    def __init__(self, deny: tuple | None = None):
        self.deny = tuple(deny or self.DEFAULT_DENY)

    def check(self, *texts) -> str | None:
        """把要执行的「动作描述」过黑名单，命中返回该模式，否则 None。"""
        blob = " ".join(str(t) for t in texts).lower()
        for p in self.deny:
            if p.lower() in blob:
                return p
        return None


class _GuardedTool(Tool):
    """包装过的工具：先鉴权 → 再审批 → 再过 sandbox → 才真执行。"""
    def __init__(self, tool: Tool, guard: "PolicyGuard", policy: ToolPolicy):
        super().__init__(tool.func, name=tool.name,
                         description=tool.description, parameters=tool.parameters)
        self._orig = tool
        self._guard = guard
        self._policy = policy

    def run(self, **kwargs):
        self._guard._precheck(self.name, kwargs, self._policy)
        return self._orig.run(**kwargs)


class PolicyGuard:
    """最小授权 + 审批 + sandbox 的执行点。

    用法：
        guard = PolicyGuard(grant="read", approver=ask_human, sandbox=DenySandbox())
        safe_tool = guard.wrap(Tool(delete_db), ToolPolicy(level="write", needs_approval=True))
        agent = MiniAgent(tools=[safe_tool], ...)   # 照旧，循环代码零改动
    """

    def __init__(self, grant: str = "read",
                 approver: Callable[[str, dict], bool] | None = None,
                 sandbox: DenySandbox | None = None):
        self.grant = grant
        self.approver = approver
        self.sandbox = sandbox

    def wrap(self, tool: Tool, policy: ToolPolicy | None = None) -> _GuardedTool:
        return _GuardedTool(tool, self, policy or ToolPolicy())

    def _precheck(self, name: str, args: dict, policy: ToolPolicy) -> None:
        # ① 最小授权：超授权即拒
        if not has_permission(self.grant, policy.level):
            raise ToolError(f"权限不足：{name} 需要 {policy.level}，当前授权 {self.grant}")
        # ② 审批：敏感工具要人点头
        if policy.needs_approval:
            if self.approver is None:
                raise ToolError(f"{name} 需要人工审批，但未配置 approver")
            if not self.approver(name, args):
                raise ToolError(f"{name} 未获人工批准")
        # ③ sandbox：危险操作拦下
        if self.sandbox is not None:
            hit = self.sandbox.check(name, args)
            if hit:
                raise ToolError(f"{name} 命中沙箱黑名单：{hit!r}")


# ---------------------------------------------------------------------------
# Prompt Injection 启发式检测
# ---------------------------------------------------------------------------

INJECTION_PATTERNS = (
    # 只留「长而固定」的话术；短中文（如「你是」）会把正常句子全判成可疑，
    # 误报率不可接受——启发式本来就该按「宁可漏报、不可误伤」设计。
    "ignore previous instructions", "disregard", "忘掉之前的指令", "ignore all",
    "无视上面的指令", "system prompt", "reveal your system", "开发者模式",
)


@dataclass
class InjectionReport:
    suspicious: bool
    matched: list = field(default_factory=list)
    score: int = 0


def detect_injection(text: str) -> InjectionReport:
    """启发式提示注入检测：数据里出现「指令式」措辞即标可疑。

    这是最粗的一层（真对抗要系统级输入/工具隔离 + 不把不可信内容当指令）。
    但先立住一个动作：把「藏在数据里的指令」和「真正的指令」分开看。
    """
    low = (text or "").lower()
    matched = [p for p in INJECTION_PATTERNS if p.lower() in low]
    return InjectionReport(suspicious=bool(matched), matched=matched, score=len(matched))