"""trace —— 可观测：Trace / 日志 / 回放（Harness 第十二块砖，第 14 章落地）。

第 13 章的 MiniAgent 只能发粗粒度事件（start/finish/error），第 14 章做可观测
四件套 log / metric / trace / replay：

- log：结构化事件序列（机器可读、人可 grep）
- metric：聚合计数（rounds / tool_calls / 耗时），拿来判断这单健康不健康
- trace：一次 run 的全过程（每次 LLM 调用、每次工具调用、每步状态）串成可回放线
- replay：把记录的过程重放，复现问题（配 ScriptedLLM 离线重跑）

思路：Tracer 不侵入 `AgentLoop.run`——（a）包装 llm，记录每一次 `chat()`；
（b）挂到 MiniAgent 的钩子上收 start/finish/error。于是「每一轮、每一次工具
调用、每一步状态」都变成带时间戳、带顺序的事件。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from harness.llm import LLMResult


@dataclass
class TraceEvent:
    """一条可观测事件：seq 保顺序、ts 记相对耗时、payload 放内容。"""
    seq: int
    ts: float                    # 相对 Tracer 开始的秒数
    type: str                    # run.start / run.finish / llm.call / llm.return ...
    payload: dict = field(default_factory=dict)


@dataclass
class Trace:
    """一次 run 的完整记录。"""
    trace_id: str
    events: list[TraceEvent] = field(default_factory=list)


class ScriptedLLM:
    """按脚本依次吐 LLMResult 的假模型：replay 的原料，也给你当离线测试替身。

    把一次真实 run 里模型返回的 LLMResult 序列录下来，喂给 ScriptedLLM，
    配上同样的工具和输入，就能在离线里复现那次 run。
    """

    def __init__(self, script: list[LLMResult]):
        self.script = list(script)

    def chat(self, messages, **kwargs):
        if not self.script:
            raise RuntimeError("ScriptedLLM 脚本耗尽：实际调用比脚本多")
        return self.script.pop(0)


class _TraceLLM:
    """包装真实 llm，把每一次 chat() 记成 llm.call / llm.return。"""
    def __init__(self, tracer: "Tracer", inner):
        self.tracer = tracer
        self._inner = inner

    def chat(self, messages, **kwargs):
        self.tracer.record("llm.call",
                           n_messages=len(messages),
                           kwargs=list(kwargs))
        t0 = time.time()
        try:
            res = self._inner.chat(messages, **kwargs)
        except Exception as e:  # noqa: BLE001
            self.tracer.record("llm.error", error=str(e))
            raise
        self.tracer.record("llm.return",
                           ms=round((time.time() - t0) * 1000, 2),
                           tool_calls=len(getattr(res, "tool_calls", []) or []),
                           content_len=len(getattr(res, "content", "") or ""))
        self.tracer.llm_results.append(res)   # 供 replay 抽取响应序列
        return res


class Tracer:
    """可观测四件套的收集端。

    用法：
        tracer = Tracer(wrap=llm, name="agent-1")
        agent = MiniAgent(llm=tracer.llm, system=..., tools=..., name="agent-1")
        agent.on(tracer.on_event)              # 收 run 的 start/finish/error
        agent.run("...")
        tracer.save("trace.jsonl")             # log
        print(tracer.metrics())                # metric
        print(tracer.timeline())               # trace（人读时间线）
        ScriptedLLM(tracer.llm_script())       # replay（离线重放原料）
    """

    def __init__(self, wrap=None, name: str = "agent"):
        self.name = name
        self.t0 = time.time()
        self.events: list[TraceEvent] = []
        self.llm_results: list[LLMResult] = []
        self._seq = 0
        self.llm = _TraceLLM(self, wrap) if wrap is not None else None

    # ---- 收集 ----
    def record(self, etype: str, **payload) -> TraceEvent:
        ev = TraceEvent(self._seq, round(time.time() - self.t0, 3), etype, payload)
        self._seq += 1
        self.events.append(ev)
        return ev

    def on_event(self, e) -> None:
        """MiniAgent 钩子兼容：把 RuntimeEvent 记成 run.* 事件。"""
        self.record("run." + e.type, **(getattr(e, "payload", {}) or {}))

    # ---- log / metric / trace / replay 四件套 ----
    def to_lines(self) -> list[str]:
        """log：结构化成 NDJSON 行。"""
        import json
        out = []
        for e in self.events:
            out.append(json.dumps({"seq": e.seq, "ts": e.ts, "type": e.type,
                                   "payload": e.payload}, ensure_ascii=False))
        return out

    def save(self, path: str = "trace.jsonl") -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.to_lines()) + ("\n" if self.events else ""))

    def metrics(self) -> dict:
        """metric：从事件里聚合出这单的健康指标。"""
        llm_returns = [e for e in self.events if e.type == "llm.return"]
        tool_calls = sum(e.payload.get("tool_calls", 0) for e in llm_returns)
        final = next((e for e in reversed(self.events)
                      if e.type.startswith("run.")), None)
        raw = final.type.split(".")[-1] if final else "unknown"
        # 事件叫 run.finish / run.error，映射回 Agent 状态 done / error
        final_state = {"finish": "done", "error": "error"}.get(raw, raw)
        return {
            "events": len(self.events),
            "rounds": len(llm_returns),          # 每一次 llm.return = 一轮
            "tool_calls": tool_calls,
            "duration_ms": round((time.time() - self.t0) * 1000, 1),
            "final_state": final_state,
        }

    def timeline(self) -> str:
        """trace：把事件序列画成人读的时间线。"""
        lines = [f"# trace {self.name}"]
        for e in self.events:
            mark = {"run.start": "▸", "run.finish": "✔", "run.error": "✘",
                    "llm.call": "→", "llm.return": "←", "llm.error": "✘"}.get(e.type, "·")
            detail = {}
            if e.type == "llm.return":
                detail = {"tool_calls": e.payload.get("tool_calls"), "ms": e.payload.get("ms")}
            elif e.type == "llm.call":
                detail = {"n_messages": e.payload.get("n_messages")}
            extra = ", ".join(f"{k}={v}" for k, v in detail.items()) if detail else ""
            lines.append(f"  +{e.ts:>7}s [{e.seq:0>2}] {mark} {e.type} {extra}".rstrip())
        return "\n".join(lines)

    def llm_script(self) -> list[LLMResult]:
        """把「模型这一步的实际产出（LLMResult 序列）」抽出来，供 ScriptedLLM 离线重放。

        注意：这里演示的是『把响应序列录下来』——真实回放还要连输入、工具结果
        一起录，第 17 章实战项目会完整做一遍。这里先立住『重放 = 用录的内容再跑』。
        """
        return list(self.llm_results)