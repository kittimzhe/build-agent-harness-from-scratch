"""深度研究项目的行为契约（无需 API）。

审阅稿点名的「空心续跑」回归：resume=True 不能只恢复步骤状态，
检索记忆（notes/向量）必须一起恢复——否则综合阶段拿到空上下文。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from harness import ScriptedLLM, LLMResult

from projects.deep_research.agent import DeepResearchAgent
from projects.deep_research.search import FakeSearchEngine

PLAN = ["LangGraph 是什么", "MCP 是什么", "它们怎么配合"]


def _agent(workdir, llm=None):
    return DeepResearchAgent(
        llm=llm or ScriptedLLM([LLMResult(content="（报告）", tool_calls=[])]),
        engine=FakeSearchEngine(),
        workdir=str(workdir),
    )


def test_crash_then_resume_restores_retrieval_memory(tmp_path):
    """崩溃在第 2 步 → 新进程 resume：步骤零重跑 + 综合上下文非空。"""
    wd = tmp_path / "wd"

    # ── 第一段：3 步计划，第 2 步崩溃 ──
    a1 = _agent(wd)
    original_step = a1._research_step

    def crash_on_step2(desc, idx):
        if idx == 1:
            raise RuntimeError("模拟崩溃：检索到一半进程挂了")
        return original_step(desc, idx)

    a1._research_step = crash_on_step2
    with pytest.raises(RuntimeError, match="模拟崩溃"):
        a1.research("LangGraph 和 MCP 有什么关系？", plan=PLAN)

    # 崩溃后：步骤 0 已 done 且笔记已落盘（每步 save，不是全程结束才 save）
    assert os.path.exists(wd / "notes.json"), "崩溃后 notes.json 不存在——每步落盘没生效"

    # ── 第二段：新进程（新 agent、新向量记忆），resume=True ──
    a2 = _agent(wd)
    result = a2.research("LangGraph 和 MCP 有什么关系？", resume=True)

    # 步骤状态：0 没重跑（保持 done），1/2 补跑完
    assert all(s.status == "done" for s in result["plan"].steps)

    # 核心：综合上下文必须非空——检索记忆被恢复了，而不是「(未检索到资料)」
    ctx = result["context"]
    assert "未检索到资料" not in ctx, f"续跑后上下文为空：{ctx!r}"
    assert "LangGraph" in ctx and "MCP" in ctx, f"上下文缺关键资料：{ctx!r}"

    # trace 里能看到恢复量
    lines = open(wd / "trace.jsonl", encoding="utf-8").read().strip().splitlines()
    assert any('"memory.restored"' in ln for ln in lines)


def test_fresh_run_context_non_empty(tmp_path):
    """正常跑（不崩溃）：上下文同样非空——这是续跑断言的基线。"""
    result = _agent(tmp_path / "wd").research("q", plan=PLAN)
    assert "未检索到资料" not in result["context"]
