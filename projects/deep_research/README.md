# 深度研究助手（Deep Research Agent）

第 17 章实战项目：把教程 01–16 的内核砖拼成一个「深度研究助手」。

## 数据流（三阶段）

```
问题 ──Phase 1 规划(10)──▶ 子问题列表
                ──Phase 2 检索(05/06/09/11/12)──▶ 搜索 + 记笔记 + 反思 + checkpoint
                ──Phase 3 综合(08/09/10)──▶ 向量取片 + 预算裁剪 + LLM 写报告
全程：trace(14) + 终止条件/护栏(15)
```

## 运行

```bash
# 离线跑通（无需 API；搜索用内置假搜索引擎、LLM 用脚本模型）
python projects/deep_research/main.py --offline

# 真实研究（需 API；先按第 01 章配好 .env）
python projects/deep_research/main.py --question "你的研究课题"
```

## 工件（跑完自动落盘）

- `checkpoint.json`：计划状态快照 → `resume=True` 断点续跑（12）
- `notes.json`：长期记忆笔记（09）
- `trace.jsonl`：可观测事件流（14）

## 怎么把它换成「真的」

| 离线替身 | 换真 | 改哪 |
| --- | --- | --- |
| `FakeSearchEngine` | Tavily / Bing / Google API | `search.py` 里加一个 `RealSearchEngine`，`make_search_tool` 签名不变 |
| `ScriptedLLM` | `LLMClient()` | `main.py --question` 走真实路径 |
| 单关键词检索 | MCP 远程搜索工具 | 把 `MCPClient.to_harness_tools()` 得到的 Tool 传给 `search_tool`（16） |