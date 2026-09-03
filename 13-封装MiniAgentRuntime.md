# 13 - 封装 Mini Agent Runtime

> 📌 **第 13 章 · 阶段五 Runtime 层（开局）** · [← 返回目录大纲](教程目录大纲.md) · [上一章 12 Checkpoint 与状态恢复 →](12-Checkpoint与状态恢复.md) · 下一章 14 可观测：Trace/日志/回放（规划中）

---

**本章课程目标：**

- 把一个分散的内核**封装成一个可复用对象**：`MiniAgent` = 状态机 + 事件循环 + 可插拔钩子。
- 掌握 **Agent 状态机**：`new → running → done | error`，并理解「非法迁移要报错」这一护栏。
- 理解**事件循环 + 钩子**：一次 `run` 就是一圈状态机，`on_event` 让上层能观察每一步——为第 14 章 trace 铺路。
- 说清 mini runtime 与 **LangGraph / OpenAI Agents SDK** 的关系：价值观一致（显式状态、可插拔、可观察），只是别人替你写好了更多。
- 落地第十一块砖：`harness/runtime.py`（`AgentState` / `RuntimeEvent` / `MiniAgent`）。

**学习建议：** demo ①–③ 用 `FakeLLM` 确定性输出、**无需 API Key**；⑤ 才走真实 LLM。本章是「装配」，代码都很薄——重点不是写了多少，而是**看清框架到底在替你做什么**。

---

## 1、从「十块砖」到「一个 Agent」

前十二章攒了十块砖，但每一块都要你手动装配：new 一个 `LLMClient`、包几个 `Tool`、再 new 一个 `AgentLoop`、跑完自己判 `stopped_by`…… 散落一地的能力，谈不上「可复用的 runtime」。

本章做最后一步封装：把「这堆砖」收进一个对象：

```python
agent = MiniAgent(system="你是周报助手", tools=[Tool(add)], name="reporter")
agent.on(lambda e: print(e.type))       # 钩子：观察每一步
out = agent.run("算一下 1+2")           # new → running → done/error
print(agent.state, agent.events)        # 状态与全程事件都可取到
```

一个 Agent 实例从此是三样东西的组合：

| 组成 | 作用 | 复用哪章 |
| --- | --- | --- |
| 状态机 | 显式标出「现在到哪了」 | 05（循环）/ 12（状态） |
| 事件循环 | 一圈状态机，内部委托 `AgentLoop` 和模型过招 | 05 |
| 钩子 | 每一步都可被上层观察 | 为 14（trace）铺路 |

---

## 2、Agent 状态机：显式 + 有护栏

```python
class AgentState:
    NEW = "new"; RUNNING = "running"; DONE = "done"; ERROR = "error"
```

合法迁移只有：`new → running`、`running → done/error`。`reset()` 回到 `new`，一个 Agent 可反复复用。**非法迁移直接抛错**——比如 `done` 状态下再 `run`（该先 `reset`），这是状态机里的护栏，和第 05 章 `max_rounds` 一样，都是「在该停的时候不让你乱走」。

> 为什么状态值那么多讲究？因为**「机器能判断的状态，就别靠人眼看日志猜」**。`agent.state == done` 是一句程序能判定的真话；「应该跑完了」是一句要人去猜的话。第 12 章说「状态是真源」，本章把状态变成了 runtime 的一等公民。

---

## 3、内核：harness/runtime.py（第十一块砖）

### 3.1 事件循环 + 钩子

```python
def on(self, hook): self.hooks.append(hook)   # 注册观察者
def _emit(self, etype, **payload):            # 发事件：记进 events + 逐钩子回调
```

一次 `run` 会在关键节点发事件：`start`（开始）、`finish`（模型自然收尾）、`error`（异常或撞护栏）。这些事件就是**第 14 章 trace 的原料**——本章先让它们能被钩住，下一章再系统化地存、查、回放。

### 3.2 run 的骨架子

```python
self._transition(RUNNING); self._emit("start", ...)
out = AgentLoop(...).run(user_input, system)   # 委托第 05 章的循环引擎
# model 收尾 → done + finish；max_rounds / 异常 → error + error 事件
```

完整实现见 [harness/runtime.py](harness/runtime.py)。

> 🧱 第十一块砖落位：内核从「一堆工具函数」进化成了「一个可复用的 Agent 对象」。到这里，你已经拥有了一个**能调用、有记忆、能循环、扛得住、说人话、懂治理、记得住、拆得动、救得回、保得住的 mini runtime**——剩下的章节（可观测、安全、协议、实战）是在它上面加「生产级」的壳。

---

## 4、对比：LangGraph / OpenAI Agents SDK

本教程不假装「我手写的比框架好」，而是要你**看懂框架在替你做什么**：

- **LangGraph**：把 Agent 的每一步流转**显式图化**（node + edge）——可视化、可分支、可挂 checkpoint。它的「图」和我们的「状态机 + 事件循环」是同一件事的两个表达：显式状态流转。
- **OpenAI Agents SDK**：`handoff`（Agent 之间转交）、`guardrail`、`tracing` 是一等公民。我们的 `on_event` 钩子就是 tracing 的极简版。

一句话：**框架 = 同一个价值观（显式状态、可插拔、可观察）+ 替你写好了更多生产细节。** 看懂 mini runtime，再看框架时你看到的不再是黑魔法，而是「原来那层是干这个的」。

---

## 5、运行本章案例

demo ①–③ 无需 `.env`，⑤ 需要（配置见 [第 01 章环境准备](01-LLM调用与环境准备.md#3、环境准备)）：

```bash
python examples/13_runtime.py
```

预期输出（①–③ 是确定性的）：

```
① 状态机：new → running → done；reset() 回到 new
  初始 state = new
  run 后 state = done | reply = 你好，周报已准备好…
  reset 后 state = new（可复用跑下一单）

② 事件循环 + 钩子：on_event 观察每一步
  钩子捕获的事件序列：start → finish
  state=done，reply=1 + 2 = 3，rounds=2

③ 护栏：模型永远要工具 → max_rounds 硬停 → state=error
  state=error
  reply=（已达到最大轮数 3，循环被护栏终止）…
  最后事件 type=error，payload={'error': '护栏终止（stopped_by=max_rounds）', ...}

④ 对比：mini runtime 在「框架」面前的什么位置
  LangGraph：…显式图化…
  OpenAI Agents SDK：…handoff + guardrail + tracing…
  本教程 MiniAgent：一条循环 + 显式状态字段 + 钩子，最薄但价值观一致

⑤ 真实 LLM：九块砖装进一个 MiniAgent
  [事件] start
  [事件] finish
  state=done，回复：37 + 5 = 42
```

> ⚠️ demo⑤ 由真实模型生成，措辞不同。**注意 demo②**：`start → finish` 中间隔着一轮工具调用，事件没有「tool_call」这一级——这正留给下一章（trace 要在 `AgentLoop` 里打更细的桩）。

---

## 6、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| `非法状态迁移：done -> running` | 同个 Agent 没 `reset` 就二次 `run` | 先 `agent.reset()` 再跑下一单 |
| 事件里没有工具调用明细 | `MiniAgent` 委托 `AgentLoop`，细粒度事件没暴露 | 第 14 章在循环里打桩（trace） |
| 想给工具加容错 | 直接把 `Tool` 换成 `ResilientTool` | `tools=[ResilientTool(add, policy=...)]` |
| 想多个 Agent 协作 | 本章是单 Agent runtime | 学 LangGraph 的图 / SDK 的 handoff，或自己发事件调度 |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 7、本章小结与下一章

✅ 你现在已经能：

- 用 `MiniAgent` 把内核封装成一个可复用对象
- 说清 Agent 状态机（new/running/done/error + 护栏 + reset）与事件循环 + 钩子
- 用 `on_event` 观察每一步，知道这些事件是 trace 的原料
- 说清 mini runtime 与 LangGraph / OpenAI Agents SDK 的「同族」关系

➡️ 下一章 **14 可观测：Trace / 日志 / 回放**（阶段五）：本章 `on_event` 只到「能钩住」，下一章回答「然后呢」——log / metric / trace / replay 四件套，把每一步的输入输出、耗时、工具调用存下来，做到事后能查、能回放、能接 Langfuse。可回[教程目录大纲](教程目录大纲.md)看全局。