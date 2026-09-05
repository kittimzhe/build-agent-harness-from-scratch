"""深度研究助手 CLI：`python projects/deep_research/main.py`

离线跑通全流程（无需 API）：
    python projects/deep_research/main.py --offline

真实联网研究（需 API，.env 配置见第 01 章）：
    python projects/deep_research/main.py --question "LangGraph 和 MCP 有什么关系"
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, HERE)

from dotenv import load_dotenv, find_dotenv  # noqa: E402

load_dotenv(find_dotenv(usecwd=True))

from harness import LLMResult, ScriptedLLM, LLMClient  # noqa: E402
from harness.llm import PROVIDERS  # noqa: E402
from agent import DeepResearchAgent  # noqa: E402
from search import FakeSearchEngine  # noqa: E402

OFFLINE_REPORT = (
    "## 研究报告\n\n"
    "### LangGraph 是什么\n\n"
    "LangGraph 是 LangChain 出的图式 Agent 编排框架，用 node 和 edge "
    "把状态流转显式地画出来。\n\n"
    "### MCP 是什么\n\n"
    "MCP（Model Context Protocol）把工具的定义和消费解耦："
    "Server 提供 tools/list 和 tools/call。\n\n"
    "### 它们怎么配合\n\n"
    "LangGraph 管 Agent 内部的状态流转，MCP 管 Agent 与外部工具的接入，"
    "两者是不同层面的脚手架，可以一起用。\n"
)


def offline_demo(workdir=".deep_research_demo"):
    """离线跑通三层数据流：无 API，确定性输出。"""
    print("=" * 66)
    print("深度研究助手 · 离线全流程（Phase 1 规划 → Phase 2 检索 → Phase 3 综合）")
    print("=" * 66)

    # 离线：脚本模型（综合阶段只调一次 LLM）+ 假搜索引擎
    agent = DeepResearchAgent(
        llm=ScriptedLLM([LLMResult(content=OFFLINE_REPORT, tool_calls=[])]),
        engine=FakeSearchEngine(),
        workdir=workdir,
    )

    question = "LangGraph 和 MCP 有什么关系？"
    # 第 4 步故意用一个语料必空的子问题，演示「空结果 → 改词重搜」的反思路径
    plan = ["LangGraph 是什么", "MCP 是什么", "它们怎么配合", "量子引力的拓扑结构"]
    result = agent.research(question, plan=plan)

    print("\n【Phase 1 规划】子问题 =", [s.description for s in result["plan"].steps])
    print("\n【Phase 2 检索】各步状态：")
    for s in result["plan"].steps:
        print(f"  [{s.status}] {s.description}")
    print("  （第 4 步语料必空 → 走『空结果→改词重搜』：见 notes.json step3）")
    print("\n【Phase 3 综合】报告：\n" + result["report"])
    print("\n【指标】", result["metrics"])
    print("\n【工件】checkpoint:", result["checkpoint"])
    print("        notes:", result["notes"])
    print("        trace:", result["trace"])

    return agent, result


def resume_demo(workdir=".deep_research_demo"):
    """断点续跑验证：新建一个 agent 实例（模拟「崩溃后新进程」），同一 checkpoint，
    done 的步骤不再重跑。"""
    print("\n" + "=" * 66)
    print("断点续跑：新进程 + resume=True 从 checkpoint 恢复，只重跑『没 done』的步骤")
    print("=" * 66)
    # 关键：新 agent、新脚本模型，但同一个 workdir —— checkpoint 是跨进程的
    fresh = DeepResearchAgent(
        llm=ScriptedLLM([LLMResult(content=OFFLINE_REPORT, tool_calls=[])]),
        engine=FakeSearchEngine(),
        workdir=workdir,
    )
    result = fresh.research("LangGraph 和 MCP 有什么关系？", resume=True)
    statuses = [f"[{s.status}]" for s in result["plan"].steps]
    print("  恢复后的步骤状态：", " ".join(statuses))
    print("  （全部 done —— checkpoint 让新进程零重跑）")
    print("  最后一条 trace 事件 final_state =",
          result["metrics"]["final_state"])
    print()


def real_demo(question):
    print("=" * 66)
    print("深度研究助手 · 真实研究（需 API）")
    print("=" * 66)
    agent = DeepResearchAgent(llm=LLMClient(), workdir=".deep_research")
    result = agent.research(question, max_steps=3)
    print("\n" + result["report"])
    print("\n【指标】", result["metrics"])
    print("【工件】", result["trace"])


def main():
    args = [a for a in sys.argv[1:]]
    if "--offline" in args:
        agent, _ = offline_demo()
        resume_demo()
        print("✅ 离线全流程 + 断点续跑验证完成（无需 API）。")
        return
    if "--question" in args:
        q = args[args.index("--question") + 1]
        real_demo(q)
        return
    # 默认：先离线跑通，若配了 API 再跑真实研究
    agent, _ = offline_demo()
    resume_demo()
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    key = PROVIDERS.get(provider, ("",))[0]
    if provider == "ollama" or os.getenv(key):
        real_demo("LangGraph 和 MCP 有什么关系？")
    else:
        print(f"\n💡 未配置 {key}，跳过真实研究。配置后：")
        print("   python projects/deep_research/main.py --question \"你的研究课题\"")


if __name__ == "__main__":
    main()