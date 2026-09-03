"""深度研究助手的检索层：离线 FakeSearchEngine + 可接真实搜索的 Tool。

把「搜索」抽成一个 Tool（签名统一），离线用确定性小语料跑通全流程；
真实场景把 engine 换成 Tavily / Bing / Google 的 API 客户端，签名不变——
这是第 16 章「协议/能力适配成 Tool」的最小实践。
"""

from __future__ import annotations

import re

from harness import Tool


class FakeSearchEngine:
    """确定性假搜索引擎：在一个小语料上做关键词出分，供离线跑通全流程。

    语料故意都用教程里的概念，既演示检索、又当复习。
    """

    CORPUS = {
        "langgraph": "LangGraph 是 LangChain 出的图式 Agent 编排框架，用 node 和 edge 把状态流转显式画出来。",
        "mcp": "MCP（Model Context Protocol）把工具的定义和消费解耦：Server 提供 tools/list 和 tools/call。",
        "checkpoint": "断点续跑依赖 Checkpoint：把 Agent 的运行状态序列化落盘，恢复时只重跑没完成的步骤。",
        "reflection": "反思（Reflection）让 Agent 失败后总结原因、换个思路重试，是给 ReAct 和 Plan-and-Execute 兜底的策略。",
        "agent memory": "Agent 记忆分短期（对话历史）和长期（文件/向量库），二者配合才有跨会话的上下文。",
        "vector": "向量检索把文本映射成向量，用余弦相似度找最相近的片段，是 RAG 的检索核心。",
        "tool use": "工具调用让模型通过 Function Calling 触发外部函数，把「会说」升级成「会做」。",
        "trace": "可观测四件套 log/metric/trace/replay：记录事件、聚合指标、串时间线、离线重放。",
        "safety": "Agent 安全三件事：终止条件、最小授权与审批、sandbox；外加提示注入防御。",
        "integration 配合 关系 orchestration": "编排与接入的配合：LangGraph 这类编排框架管 Agent 内部状态流转，MCP 这类协议管外部工具接入，二者正交、可叠加使用。",
    }

    def search(self, query: str, top_k: int = 3) -> list[str]:
        terms = _tokens(query)
        scored = []
        for key, doc in self.CORPUS.items():
            blob = (key + " " + doc).lower()
            score = sum(1 for t in terms if t and t in blob)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: -x[0])
        return [doc for _, doc in scored[:top_k]] or ["（无相关结果）"]


def _tokens(text: str) -> list[str]:
    """轻量分词：英文/数字按词切，中文按 2-gram 切。

    中文没有空格，连续一段「它们怎么配合」若整段当词会匹配不到『配合』这个子串；
    拆成 2-gram 后，『配合』就能命中语料里的关键词。够离线检索用。
    """
    toks: list[str] = []
    for run in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", (text or "").lower()):
        if run[0].isascii():
            toks.append(run)
        elif len(run) == 1:
            toks.append(run)
        else:
            toks += [run[i:i + 2] for i in range(len(run) - 1)]
    return toks


def make_search_tool(engine: FakeSearchEngine | None = None) -> Tool:
    """把搜索引擎包装成一条 Tool：MiniAgent / Plan 执行器都能直接调。"""
    engine = engine or FakeSearchEngine()

    def search(query: str) -> str:
        results = engine.search(query)
        if results == ["（无相关结果）"]:
            return "（无相关结果）"
        return "\n".join(f"{i + 1}. {r}" for i, r in enumerate(results))

    return Tool(search, name="search", description="搜索一个关键词，返回相关片段")