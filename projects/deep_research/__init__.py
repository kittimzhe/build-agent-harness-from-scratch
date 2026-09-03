"""deep_research —— 第 17 章实战项目：深度研究助手 Agent。

把教程 01–16 的块拼成一个能真正跑通的项目：
  Phase 1 规划（10 → make_plan）→ Phase 2 检索（05/06/09/11/12 → search + 记忆 + 反思
  + checkpoint）→ Phase 3 综合（08/10 → assemble + LLM 写报告），全程 trace（14）+ 护栏（15）。

离线设计：search 层抽成 FakeSearchEngine（确定性小语料），真实场景换成 Tavily/Bing
只改 Tool 签名；LLM 层用 ScriptedLLM 也能跑通全流程、无需 API Key。
"""