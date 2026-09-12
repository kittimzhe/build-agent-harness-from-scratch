"""DeepResearchAgent —— 把 01–16 的砖拼成一个深度研究助手。

数据流（三阶段）：
  Phase 1 规划：make_plan 把研究课题拆成子问题（10）
  Phase 2 检索：每个子问题 search → 记笔记(文件记忆) + 存向量(检索去重)（09）；
                空结果走确定性改词再试（11 反思的简化）；run_plan_with_checkpoint
                每步落盘、断点续跑（12）
  Phase 3 综合：向量检索取最相关片段（09）→ 预算裁剪（08）→ LLM 写报告
  全程：Tracer 落 trace.jsonl（14）；StopConditions + 计划步数 = 终止护栏（15）

离线设计：注入 FakeSearchEngine + ScriptedLLM 即可无 API 跑通全流程；
真实路径注入 LLMClient + 真实搜索 Tool，代码同一份。
"""

from __future__ import annotations

import os

from harness import (
    LLMClient, LLMResult, Plan, PlanStep, make_plan, run_plan_with_checkpoint,
    FileMemory, VectorMemory, Tracer, StopConditions, Tool,
)
try:  # 兼容 `python -m projects.deep_research.main` 与直接运行两种形态
    from .search import FakeSearchEngine, make_search_tool, _tokens
except ImportError:
    from search import FakeSearchEngine, make_search_tool, _tokens


class DeepResearchAgent:
    """深度研究助手。核心 API：research(question) -> {report, plan, metrics, ...}。"""

    def __init__(self, llm=None, engine=None, workdir: str = ".deep_research",
                 name: str = "deep-research"):
        base_llm = llm or LLMClient()
        self.tracer = Tracer(wrap=base_llm, name=name)   # 14：包装 llm，全程落 trace
        self.llm = self.tracer.llm                        # 所有 LLM 调用自动被观测

        self.engine = engine or FakeSearchEngine()
        self.search_tool = make_search_tool(self.engine)  # 离线/真实，签名统一

        self.workdir = workdir
        os.makedirs(workdir, exist_ok=True)
        self.checkpoint_path = os.path.join(workdir, "checkpoint.json")
        self.notes_path = os.path.join(workdir, "notes.json")
        self.trace_path = os.path.join(workdir, "trace.jsonl")

        self.notes = FileMemory(self.notes_path)           # 09：长期记忆（笔记）
        self.vec = VectorMemory()                          # 09：向量记忆（检索去重）
        self.limits = StopConditions(max_rounds=8, max_output_chars=4000)  # 15：护栏
        #                                    ^ 计划步数预算（检索前拦）；max_steps 默认 3，超过 8 步才会截断

    # ------------------------------------------------------------------ #
    # Phase 1：规划（10）
    # ------------------------------------------------------------------ #
    def _plan(self, question: str, max_steps: int, plan=None):
        """plan 可显式注入（离线/复用）；否则走 make_plan（真实 LLM）。"""
        if plan is not None:
            return Plan(goal=question, steps=[PlanStep(s) for s in plan])
        return make_plan(self.llm, question, max_steps=max_steps)

    # ------------------------------------------------------------------ #
    # Phase 2：检索（05/06/09/11/12）
    # ------------------------------------------------------------------ #
    def _reformulate(self, desc: str) -> str:
        """确定性改词（反思的离线简化版）：去停用 gram、留内容 gram。

        真实路径可换成第 11 章 retry_with_reflection（用 LLM 反思出更好的查询）。
        """
        stop = {"如何", "什么", "是什", "为什", "怎么", "它们", "一个", "怎样",
                "哪些", "介绍", "对比", "区别", "关系", "研究", "是什么", "么配",
                "们怎", "它与", "与它"}
        tokens = [t for t in _tokens(desc) if t not in stop and len(t) >= 2]
        return " ".join(tokens[:4]) if tokens else desc

    def _search(self, query: str) -> str:
        """带 trace 的检索：工具名 / 参数 / 返回都进 trace.jsonl（14）。"""
        self.tracer.record("tool.start", tool="search", args={"query": query})
        out = self.search_tool.run(query=query)
        self.tracer.record("tool.return", tool="search", output=str(out)[:500])
        return out

    def _research_step(self, desc: str, idx: int) -> str:
        """一步研究：搜索 → （空结果则改词再搜）→ 记笔记 + 存向量。"""
        text = self._search(desc)
        trail = ""
        if text.strip() == "（无相关结果）":
            alt = self._reformulate(desc)                  # 11：失败换思路（确定性简化）
            text = self._search(alt)
            trail = f"（空结果→改词重搜：{alt}）"
        note = f"{desc}\n{text}{trail}"
        self.notes.remember(f"step{idx}", note)            # 09：文件记忆
        self.notes.save()                                  # 每步落盘：崩溃后笔记不丢（12 的 at-least-once 精神）
        self.vec.add(note, meta={"step": desc, "idx": idx})  # 09：向量记忆（meta 用 dict）
        return text

    def _restore_memory(self, plan) -> int:
        """续跑时重建检索记忆：VectorMemory 是内存态，新进程里是空的。

        崩溃前已 done 的步骤，其笔记在 notes.json（_research_step 每步落盘），
        步骤结果也在 checkpoint 里。这里把两者灌回向量记忆，否则综合阶段
        只能拿到「(未检索到资料)」——checkpoint 恢复的不该只有步骤状态。
        返回重建的条数。
        """
        restored = 0
        for i, step in enumerate(plan.steps):
            if step.status != "done":
                continue
            note = self.notes.recall(f"step{i}")
            if note is None:
                note = step.result or step.description   # 兜底：老版本没同步 notes
            if note:
                self.vec.add(note, meta={"step": step.description, "idx": i})
                restored += 1
        return restored

    # ------------------------------------------------------------------ #
    # Phase 3：综合（08/09/10）
    # ------------------------------------------------------------------ #
    def _assemble_context(self, question: str, top_k: int = 5, budget_chars: int = 2400) -> str:
        """从向量记忆按问题取最相关片段（09），再按字符预算粗裁（08 思路）。"""
        hits = self.vec.search(question, top_k=top_k)
        parts = [f"[{h['meta']}] {h['text']}" for h in hits]
        combined = "\n\n".join(parts) if parts else "(未检索到资料)"
        if len(combined) > budget_chars:                    # 08：Context 治理
            combined = combined[:budget_chars] + "\n…(已截断)"
        return combined

    def _synthesize(self, question: str, context: str) -> str:
        system = "你是一名研究助手。基于给定资料写一份结构化研究报告（要点式，含小标题，别编造资料里没有的内容）。"
        user = f"研究课题：{question}\n\n资料：\n{context}\n\n请给出研究报告。"
        out = self.llm.chat([{"role": "system", "content": system},
                             {"role": "user", "content": user}])
        return out.content or ""

    # ------------------------------------------------------------------ #
    def research(self, question: str, plan=None, resume: bool = False,
                 max_steps: int = 3) -> dict:
        """跑一次完整研究。返回报告与全程工件。"""
        self.tracer.record("run.start", question=question)   # 14：流程编排自己记生命周期

        # 断点续跑（12）：有 checkpoint 就从盘上恢复
        if resume and os.path.exists(self.checkpoint_path):
            from harness import load_checkpoint
            p = load_checkpoint(self.checkpoint_path)
            restored = self._restore_memory(p)              # 检索记忆也要恢复，不只步骤状态
            self.tracer.record("memory.restored", notes=restored)  # 14：恢复量进 trace
        else:
            p = self._plan(question, max_steps=max_steps, plan=plan)

        # 15：终止条件①——计划步数预算，在检索循环**之前**拦（超预算截断，不烧检索）
        step_reason = self.limits.check(rounds=len(p.steps))
        if step_reason:
            p.steps = p.steps[:self.limits.max_rounds]

        # Phase 2：每步落盘执行（12）
        run_plan_with_checkpoint(p, self._research_step, self.checkpoint_path)

        # Phase 3：综合 + 写报告
        context = self._assemble_context(question)
        report = self._synthesize(question, context)

        # 15：终止条件②——输出字符预算，报告写完后检查
        reason = self.limits.check(rounds=0, output_text=report)
        if reason:
            report = f"{report}\n\n（⚠️ 触发终止条件：{reason}）"

        self.tracer.record("run.finish", report_len=len(report))  # 14
        # 落盘四大工件
        self.tracer.save(self.trace_path)         # 14：trace
        self.notes.save()                         # 09：长期记忆
        return {
            "report": report,
            "context": context,          # 综合阶段实际用到的资料（评测/调试可查）
            "plan": p,
            "metrics": self.tracer.metrics(),
            "checkpoint": self.checkpoint_path,
            "notes": self.notes_path,
            "trace": self.trace_path,
        }