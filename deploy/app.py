"""第 18 章：把深度研究助手包成可上线 HTTP 服务（FastAPI）。

运行（本地）：
    pip install -r requirements-full.txt
    uvicorn deploy.app:app --reload

冒烟测试（无 API，离线）：
    DEEP_RESEARCH_OFFLINE=1 uvicorn deploy.app:app --port 8000
    curl http://127.0.0.1:8000/health
    curl -X POST http://127.0.0.1:8000/research \
         -H 'Content-Type: application/json' \
         -d '{"question": "LangGraph 和 MCP 有什么关系？"}'

设计原则（延续全书）：
- 无状态：每个请求独立建一个 DeepResearchAgent，避免跨用户的记忆/检查点串味；
- 离线可测：DEEP_RESEARCH_OFFLINE=1 用 ScriptedLLM + FakeSearchEngine 冒烟；
- 只暴露协议：请求/响应用 Pydantic 模型定死，内核（harness）的私有结构不流出 HTTP。
"""

from __future__ import annotations

import os
import sys
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))          # deploy/
ROOT = os.path.dirname(HERE)                               # 仓库根
sys.path.insert(0, ROOT)

from dotenv import load_dotenv, find_dotenv                # noqa: E402
load_dotenv(find_dotenv(usecwd=True))

from fastapi import FastAPI                                # noqa: E402
from pydantic import BaseModel, Field                      # noqa: E402

from harness import LLMClient, ScriptedLLM, LLMResult      # noqa: E402
from projects.deep_research.agent import DeepResearchAgent  # noqa: E402
from projects.deep_research.search import FakeSearchEngine  # noqa: E402


class ResearchRequest(BaseModel):
    """/research 的请求体：研究课题 + 可选计划 + 步数上限 + 可选续跑 id。"""
    question: str = Field(..., description="研究课题")
    plan: Optional[list[str]] = Field(None, description="可选：显式子问题（离线/复用）")
    max_steps: int = Field(3, ge=1, le=8, description="最多拆分几步")
    checkpoint_id: Optional[str] = Field(None, description="可选：续跑上次请求返回的 id（断点续跑）")


class ResearchResponse(BaseModel):
    """/research 的响应体：报告 + 指标 + 工件路径（只露协议，不露内核私有结构）。"""
    report: str
    final_state: str
    rounds: int
    tool_calls: int
    trace_file: str
    checkpoint_id: str


app = FastAPI(title="Deep Research Agent", version="1.0.0")


def _build_agent(workdir: str) -> DeepResearchAgent:
    """每个请求建一个独立 agent + 独立 workdir（无状态：文件层也不串味）。"""
    if os.getenv("DEEP_RESEARCH_OFFLINE") == "1":
        # 两条脚本：① 规划阶段 structured_chat 要的步骤 JSON ② 综合阶段要的报告
        llm: object = ScriptedLLM([
            LLMResult(content='{"steps": ["LangGraph 是什么", "MCP 是什么", "它们怎么配合"]}',
                      tool_calls=[]),
            LLMResult(content="## 报告（离线冒烟）\n服务链路打通：请求 → 规划 → 检索 → 综合 → 响应。",
                      tool_calls=[]),
        ])
        return DeepResearchAgent(llm=llm, engine=FakeSearchEngine(), workdir=workdir)
    return DeepResearchAgent(llm=LLMClient(), workdir=workdir)


def _workdir_for(checkpoint_id: Optional[str]) -> str:
    """无 checkpoint_id → 新建 base/req-<uuid>；有 → 复用该目录（断点续跑）。

    每请求独立目录：并发请求互不覆盖 checkpoint/notes/trace（「无状态」落在文件层）。
    """
    import uuid
    base = os.getenv("WORKDIR_BASE", ".deep_research")
    if checkpoint_id:
        # 只允许复用本 base 下的目录名，防路径穿越
        safe = os.path.basename(checkpoint_id)
        d = os.path.join(base, safe)
    else:
        d = os.path.join(base, f"req-{uuid.uuid4().hex[:12]}")
    os.makedirs(d, exist_ok=True)
    return d


@app.get("/health")
def health() -> dict:
    """存活探针：负载均衡 / 容器编排用（编排器周期打这个端点判断实例活没活）。"""
    return {"status": "ok", "offline": os.getenv("DEEP_RESEARCH_OFFLINE") == "1"}


@app.post("/research", response_model=ResearchResponse)
def research(req: ResearchRequest) -> ResearchResponse:
    """跑一次深度研究。每请求独立 workdir；要续跑就带上响应里返回的 checkpoint_id。"""
    workdir = _workdir_for(req.checkpoint_id)
    agent = _build_agent(workdir)
    result = agent.research(req.question, plan=req.plan, max_steps=req.max_steps,
                            resume=bool(req.checkpoint_id))
    m = result["metrics"]
    return ResearchResponse(
        report=result["report"],
        final_state=m["final_state"],
        rounds=m["rounds"],
        tool_calls=m["tool_calls"],
        trace_file=result["trace"],
        checkpoint_id=os.path.basename(workdir),
    )