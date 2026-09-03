# 16 - MCP / A2A / Skills 接入

> 📌 **第 16 章 · 阶段六 Protocol 与实战（开局）** · [← 返回目录大纲](教程目录大纲.md) · [上一章 15 终止条件·权限·安全 →](15-终止条件权限安全.md) · 下一章 17 实战项目：端到端 Mini Agent（规划中）

---

**本章课程目标：**

- 分清三种「接进真实世界」的协议，各自解决什么：**MCP** 接工具生态、**A2A** 接别的 Agent、**Skills** 接知识资产。
- 掌握它们的**共同接入缝**：都把自己「适配成本框架的 `Tool`」，于是 `MiniAgent` 的调用面统一。
- 看懂 MCP 的「谁定义 / 谁消费」解耦，A2A 的「专家也是能力」，Skills 的「按需挂载、别一次塞满」。
- 落地第十四块砖：`harness/protocol.py`（`MCPTool` / `MCPServer` / `MCPClient` / `AgentEndpoint` / `a2a_tool` / `Skill` / `SkillLibrary`）。

**学习建议：** 本章全部 demo **不需要 API Key**（协议交互用 `FakeLLM` 确定性演示）。这是「学前脚压线」的一章——三个协议都只传「形状」，不做完整 spec 兼容，先看懂分工与接入缝。

---

## 1、三个协议，三句人话

| 协议 | 接什么 | 一句话 |
| --- | --- | --- |
| **MCP**（Model Context Protocol） | 工具生态 | 谁定义工具（Server）、谁用工具（Client）解耦 |
| **A2A**（Agent-to-Agent） | 别的 Agent | 专家/同事也是可调用的能力 |
| **Skills** | 知识资产 | 提示词 + 工具 + 用法打包，按需挂载 |

它们不是竞争关系，是**同一个世界里三种不同的接入缝**：MCP 让你吃到别人做好的工具，A2A 让你雇到别的 Agent，Skills 让你把「怎么做一件事」沉淀成可复用资产。

---

## 2、MCP：工具「谁定义」与「谁消费」解耦

MCP 核心就是两个端点：

```python
tools/list    # 这个 server 有什么工具（name/description/parameters）
tools/call    # 调某个工具，回 {content:[{type:"text",text:...}]}
```

Server 管定义，Client 管消费。关键在于 **`MCPClient.to_harness_tools()`**：把远程 MCP 工具**适配成本框架的 `Tool`**，于是 `MiniAgent(tools=...)` 零改动就能调它们——模型根本不知道（也不该知道）工具在本地还是几百公里外。

> 真 MCP 是 JSON-RPC over stdio/SSE/HTTP，有完整的 envelope、多 content 类型、资源/提示词列表。本章 `MCPServer.handle` 直接方法名分派，只传协议形状——**看懂这一步，看官方 SDK 就只是「多了一堆序列化细节」**。

---

## 3、A2A：专家也是一种「工具」

```python
expert = MiniAgent(..., name="expert")
ask_expert = a2a_tool(AgentEndpoint(expert, "expert"))
```

`a2a_tool` 把「给另一个 Agent 发消息、拿回答」包装成一条 `Tool`。于是总协调 Agent 调 `ask_expert`，和调 `get_weather` 是同一个动作：**都是「跑一下、拿结果」**。这一下把「差一个工具」和「差一个专家」拉平了。

> A2A 的完整形态（agent card 发现、任务生命周期、流式、能力协商）生产里很厚；本章 `AgentEndpoint.send` 只留「发消息拿结果」这条最核心的线。

---

## 4、Skills：按需挂载，别一次塞满

```python
lib = SkillLibrary()
lib.add(Skill(name="report", description="生成周报",
              prompt="你是周报专家：先拉数据再算总额再画图。",
              tools=[Tool(get_weather, ...)]))
lib.catalog()      # 给模型看：- report: 生成周报
prompt, tools = lib.activate("report")   # 挂载：拿 prompt 片段 + 工具列表
```

Skills 把「提示词 + 工具 + 用法说明」打包成资产；Agent 用 `catalog()` 知道有哪些技能，用 `activate()` 按需取用。**对比反面**：把所有工具的 schema 一次性塞进 system prompt——浪费 token、还互相干扰。按需挂载，才挂得上、挂得对。

---

## 5、内核：harness/protocol.py（第十四块砖）

- `MCPTool` / `MCPServer` / `MCPClient`：MCP 的 server 侧定义与 client 侧适配。
- `AgentEndpoint` / `a2a_tool`：把另一个 Agent 包装成工具。
- `Skill` / `SkillLibrary`：技能资产的打包与按需挂载。

完整实现见 [harness/protocol.py](harness/protocol.py)。

> 🧱 第十四块砖落位：内核的地界从「单机」扩到「接外部」。外部工具（MCP）可复用第 15 章 `ToolPolicy` 做权限，可复用第 06 章 `ResilientTool` 做容错——**协议是通道，能力是积木**。

---

## 6、串联：协议与前面每一章

- **05 / 13**：所有协议最终都落到 `Tool`，`MiniAgent` 调用面统一——这是本章的「共同接入缝」。
- **06 / 15**：MCP 工具适配成 `Tool` 后，`ResilientTool` / `PolicyGuard` 照常能包它。
- **09**：Skills 的 prompt+工具 是「可复用知识」，存储层可用 `FileMemory` 落盘。
- **14**：外部调用是长尾耗时 + 故障源，`Tracer` 能记下 MCP/A2A 的每一跳。
- **17**：实战项目会把这三样串起来——一个 Agent 经 MCP 查天气、经 A2A 问专家、按 skill 出报告。

---

## 7、运行本章案例

无需 `.env`：

```bash
python examples/16_protocol.py
```

预期输出（全部确定性）：

```
① MCP：谁定义工具（server）、谁用工具（client）解耦
  tools/list → [{'name': 'get_weather', 'description': '查天气', 'parameters': {...}}]
  tools/call → {'content': [{'type': 'text', 'text': '北京：晴 25℃'}]}

② MCP 接入 MiniAgent：远程工具被适配成本框架 Tool，模型无感知
  适配后的工具：['get_weather']（就是普通 Tool）
  reply=上海是晴天，25℃

③ A2A：把「另一个 Agent」包装成工具，当专家来调
  专家被包装成工具：ask_expert
  boss 最终回复：按照专家的说法，答案是 42

④ Skills：把「提示词 + 工具 + 用法」打包成资产，按需挂载
  catalog 给模型看：
    - report: 生成周报
    - translate: 多语言翻译
  挂载 report：prompt[你是周报专家：先拉数据…] + tools=['get_weather']

⑤ 同一个世界，三种接入缝
  MCP / A2A / Skills …
```

> **盯 demo② 和 ③**：② 里 `MiniAgent` 调 `get_weather` 时完全不知道它在 MCP server 上——位置透明；③ 里 boss 调 `ask_expert` 和调一个函数是同一个姿势——能力透明。这两个「透明」就是本章要你记住的东西。

---

## 8、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| `tools/call` 回 `unknown tool: xxx` | 模型调了 server 没定义的工具 | 对齐 `tools/list` 返回的名字 |
| MCP 工具在 `MiniAgent` 里参数对不上 | 远程给的 parameters 与 handler 不一致 | 让 server 的 schema 与 handler 签名一致 |
| A2A 调用没回应 | 对方 agent 没跑通 / 回复为空 | 检查 endpoint.agent 的状态与 reply |
| `activate` 报 `unknown skill` | 技能名拼错 / 没 add | 看 `catalog()` 里实际有哪些 |
| 想给外部工具加权限 | MCP 适配后没包 guard | `PolicyGuard.wrap(mcp_tool, ToolPolicy(...))` |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 9、本章小结与下一章

✅ 你现在已经能：

- 说清 MCP / A2A / Skills 各接什么、共同接入缝是「适配成 Tool」
- 用 `MCPServer`/`MCPClient` 演示工具的解耦，用 `to_harness_tools()` 把远程工具接进 `MiniAgent`
- 用 `a2a_tool` 把另一个 Agent 当专家调
- 用 `SkillLibrary` 做技能资产的 catalog + 按需 activate

➡️ 下一章 [**17 实战项目：深度研究助手 Agent →**](17-实战项目深度研究助手.md)（阶段六）：把前十六章的**每一块砖**串成一个真实项目——一个能联网搜索、能做 RAG、能多步规划出报告、能断点续跑、带 trace 和权限的深度研究助手，从 0 到能跑。可回[教程目录大纲](教程目录大纲.md)看全局。