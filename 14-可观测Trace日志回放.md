# 14 - 可观测：Trace / 日志 / 回放

> 📌 **第 14 章 · 阶段五 Runtime 层** · [← 返回目录大纲](教程目录大纲.md) · [上一章 13 封装 Mini Agent Runtime →](13-封装MiniAgentRuntime.md) · 下一章 15 终止条件·权限·安全（规划中）

---

**本章课程目标：**

- 分清可观测**四件套**：log（记录）、metric（聚合）、trace（串成线）、replay（重放）。
- 掌握「不侵入 `AgentLoop`」的埋点方式：**包装 llm 记每次调用 + 挂 MiniAgent 钩子收状态**。
- 会看/会算：结构化事件 → 时间线 → 健康指标。
- 理解 **replay** 的本质：把录下的模型响应序列喂给 `ScriptedLLM`，离线复现问题。
- 说清**接入 Langfuse** 的 hook 在哪（记到什么、记到哪是两回事）。
- 落地第十二块砖：`harness/trace.py`（`TraceEvent` / `Trace` / `Tracer` / `ScriptedLLM`）。

**学习建议：** demo ①–④ 用 `FakeLLM` 确定性输出、**无需 API Key**；⑥ 才走真实 LLM。本章是第 13 章钩子的系统化——上一章「能钩住」，这一章「钩住之后干什么」。

---

## 1、log / metric / trace / replay 四件套

一本书里常把这四个词混着说，先一行一个立住：

| 工具 | 问的是什么 | 产物 | 例子 |
| --- | --- | --- | --- |
| **log** | 发生了什么 | 一条条带序号的记录 | `llm.return tool_calls=1 ms=3.2` |
| **metric** | 整体健康吗 | 聚合数字 | `rounds=2, tool_calls=1, final=done` |
| **trace** | 这一路怎么走的 | 按顺序串起来的事件线 | `start → llm.call → llm.return → finish` |
| **replay** | 能不能复现 | 用录下的输入/响应重跑一遍 | `ScriptedLLM` 离线重放 |

一句话：**log 是原料，metric 是总结，trace 是叙事，replay 是回放。** 原料记全了，后三样都能从它派生。

---

## 2、不侵入 AgentLoop，怎么把每一步记下来

第 13 章的 `AgentLoop` 是个黑盒（我们刻意不改它的签名）。那 trace 怎么拿到「每一轮、每一次工具调用」的细节？两个 hook，都不用改循环：

1. **包装 llm**：`Tracer(wrap=llm)` 返回一个 `tracer.llm`，它的 `chat()` 在调用前后各记一条事件（`llm.call` / `llm.return`）——每调一次 chat 就是一轮，结果里 `tool_calls` 的个数就是这一轮要了几次工具。
2. **挂 MiniAgent 钩子**：`agent.on(tracer.on_event)`，把 `start/finish/error` 收成 `run.*` 事件。

于是「状态（run.*）+ 计算（llm.*）」拼成一条完整时间线，`AgentLoop.run` 一个字没改。

> 这正是不改内核实现在做扩展的姿势：**能力走包装，不走侵入**。第 15 章的权限、第 16 章的协议，还会再用这招。

---

## 3、内核：harness/trace.py（第十二块砖）

- `TraceEvent`：`seq`（保序）+ `ts`（相对耗时）+ `type` + `payload`。
- `Tracer`：收集端，提供 `to_lines()`（log）、`metrics()`（metric）、`timeline()`（trace）、`llm_script()`（replay 原料）。
- `ScriptedLLM`：按脚本依次吐 `LLMResult` 的假模型——**回放/离线测试的利器**。

关键几步：

```python
tracer = Tracer(wrap=llm, name="calc")
agent = MiniAgent(llm=tracer.llm, tools=[Tool(add)], name="calc")
agent.on(tracer.on_event)
agent.run("算 1+2")

tracer.save("trace.jsonl")     # log
tracer.metrics()               # metric
tracer.timeline()              # trace

script = tracer.llm_script()                         # 录下模型响应序列
MiniAgent(llm=ScriptedLLM(script), ...).run("算 1+2") # replay：离线复现
```

完整实现见 [harness/trace.py](harness/trace.py)。

> 🧱 第十二块砖落位：runtime 从此「看得见」——出了 bug 不再是抓瞎，而是按 trace 定位到第几轮、第几次工具调用。可观测是所有生产级 Agent 的底线。

---

## 4、接入 Langfuse（或其他观测平台）

Langfuse 的 SDK 本质也是 span 记录（`trace → generation/span`）。我们的 `Tracer.record` 每条事件都能映射成它的一个 span：

- `run.start/finish` → trace 的起止
- `llm.call/return` → generation span（模型调用 + 耗时 + 输出）
- `tool_calls` 计数 → span 的 metadata

**hook 已经在了**（`on_event` / `record`），剩下的只是「记到哪」——换成 Langfuse SDK 的 callback 是同一思路。本章不引外部依赖，先把「该记什么」立住。

---

## 5、运行本章案例

demo ①–④ 无需 `.env`，⑥ 需要（配置见 [第 01 章环境准备](01-LLM调用与环境准备.md#3、环境准备)）：

```bash
python examples/14_trace.py
```

预期输出（①–⑤ 思路一致，⑥ 由真实模型生成）：

```
① log：结构化事件（NDJSON，机器可读、人可 grep）
  {"seq": 0, "ts": 0.0, "type": "run.start", "payload": {...}}
  {"seq": 1, "ts": 0.012, "type": "llm.call", "payload": {"n_messages": 2, ...}}
  {"seq": 2, "ts": 0.014, "type": "llm.return", "payload": {"ms": 1.2, "tool_calls": 1, ...}}
  {"seq": 3, "ts": 0.015, "type": "llm.call", "payload": {...}}
  {"seq": 4, "ts": 0.016, "type": "llm.return", "payload": {"ms": 0.8, "tool_calls": 0, ...}}
  {"seq": 5, "ts": 0.017, "type": "run.finish", "payload": {...}}

② metric：从事件聚合出这单的健康指标
  events=6  rounds=2  tool_calls=1
  duration_ms=…  final_state=done

③ trace：时间线
  # trace calc
    + 0.000s [00] ▸ run.start
    + 0.012s [01] → llm.call n_messages=2
    + 0.014s [02] ← llm.return tool_calls=1 ms=…
    …

④ replay：把录下的 LLM 响应序列，用 ScriptedLLM 离线重放
  第一遍：reply=1 + 2 = 3，录下 2 个 LLMResult
  重放  ：reply=1 + 2 = 3
  一致？True（重放的威力：离线复现问题）

⑤ 接入 Langfuse：Tracer 的事件，就是现成的接入点
  …
```

> ⚠️ 具体毫秒数每次不同，这是正常的（`ts/ms` 是真实计时）。**盯两个点**：demo① 里 `tool_calls=1` 出现在第一轮 `llm.return`（模型要了一次 add）；demo④ 里 `一致？True`（replay 忠实复现）。

---

## 6、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| timeline 里没有 `llm.*` 事件 | 没把 `tracer.llm` 传进 MiniAgent，只挂了钩子 | `MiniAgent(llm=tracer.llm, ...)` 而非原 llm |
| 事件里没有 run 状态 | 忘了 `agent.on(tracer.on_event)` | 补上这一行 |
| replay 结果和第一遍不一致 | 录的响应序列不完整 / 工具行为变了 | 确认 `llm_script()` 长度、工具幂等 |
| `ScriptedLLM 脚本耗尽` | 重放时的调用次数比录的时候多 | 检查 max_rounds、system 是否一致 |
| 想接 Langfuse 却不知从哪下手 | 没分清「记什么」和「记到哪」 | 先跑通 Tracer 的 events，再换 SDK callback |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 7、本章小结与下一章

✅ 你现在已经能：

- 分清 log / metric / trace / replay 四件套各问什么
- 用「包装 llm + 挂 MiniAgent 钩子」不侵入地收集每一步
- 用 `Tracer` 出 NDJSON（log）、指标（metric）、时间线（trace）
- 用 `ScriptedLLM` 离线重放，复现问题
- 说清接入 Langfuse 的 hook 在哪

➡️ 下一章 **15 终止条件 · 权限 · 安全**（阶段五收官）：现在 Agent 看得见、跑得动，但**它也可能被 prompt 注入、乱调工具、越权删库**——下一章补最后一道防线：终止条件、最小授权、人工审批、sandbox。可回[教程目录大纲](教程目录大纲.md)看全局。