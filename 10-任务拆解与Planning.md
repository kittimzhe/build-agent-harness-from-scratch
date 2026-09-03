# 10 - 任务拆解与 Planning

> 📌 **第 10 章 · 阶段四 State 层（开局）** · [← 返回目录大纲](教程目录大纲.md) · [上一章 09 记忆体系 →](09-记忆体系.md) · 下一章 11 失败策略与反思（规划中）

---

**本章课程目标：**

- 分清两种干活范式：**ReAct**（第 05 章 `AgentLoop`，边想边做）和 **Plan-and-Execute**（先列计划、再逐步执行），并说出各自的适用场景与取舍。
- 落地「计划」这个一等对象：`Plan` / `PlanStep`——让「要做什么」变成可推进、可观察、可审查的状态。
- 复用第 07 章的结构化输出：`make_plan` 让 LLM 吐出 `{"steps": [...]}` 这样程序能接住的步骤清单，而不是一段散文。
- 交代清楚「失败即停」的用意，为第 11 章失败策略与反思留钩子。
- 落地第八块砖：`harness/planning.py`（`Plan` / `PlanStep` / `make_plan` / `execute_plan`）。

**学习建议：** demo ①–④ 用 `FakePlanner` 确定性输出、**无需 API Key**；⑤ 才走真实 LLM。本章的「先列清单再执行」和 05 章的「每轮现想下一步」是一对姊妹，把两者放一起看才能选对范式。

---

## 1、两种范式：ReAct 与 Plan-and-Execute

第 05 章我们手写的 `AgentLoop` 是 **ReAct**（think → act → observe 循环），它的特点是**没有全局计划**，模型每轮只看历史、决定「下一步」：

```
think → 调工具(读数据库) → observe → think → 调工具(算平均值) → … → 出答案
```

本章引入 **Plan-and-Execute**（P&E）：先把目标拆成一份步骤清单，再逐步执行、逐条打钩：

```
make_plan("做一个销售周报")          # ① 先规划：出一份步骤清单
  → 1. 查本周订单  2. 算总额  3. 画柱状图  4. 写结论  5. 发邮件
execute_plan(plan)                   # ② 再执行：逐步推进、每步状态可见
```

两者的本质区别，一个词说清：**ReAct 把「计划」藏在每轮决策里，P&E 把「计划」提到台面上变成显式对象。**

| | ReAct（05） | Plan-and-Execute（10） |
| --- | --- | --- |
| 计划 | 隐式，每轮现想 | 显式，先出一份清单 |
| 中间过程 | 只留对话历史 | 有 `Plan.progress()` 可看「打到第几钩」 |
| 纠偏 | 天然每轮纠偏 | 计划错了要**重规划**（代价高） |
| 适合 | 路径不确定、探索性 | 目标清晰、步骤可预判 |
| 内核 | `AgentLoop.run` | `make_plan` + `execute_plan` |

> 关键取舍一句话：**计划越好，P&E 越省（每步都不用重新想全局）；计划越可能错，越该退回 ReAct（随时纠偏）。** 现实里两者常混用——先 P&E 出大纲，执行时每一步内部再跑一个小 ReAct。

---

## 2、为什么「计划」要变成一等对象

「先别急着写代码，先把要做什么列个清单」——这句话对人成立，对 Agent 也成立。但前提是清单得是**数据**，不是埋在 prompt 里的散文：

```python
plan = Plan(goal="规划三日旅行", steps=["查天气", "订酒店", "买票", "写行程表"])
plan.progress()
# [ ] 查天气
# [ ] 订酒店
# [ ] 买票
# [ ] 写行程表
plan.mark_done(0, "天气晴，21°C")
# [x] 查天气   ← 状态可见、可审查
```

一份可推进的 Plan 至少带来三样 ReAct 给不了的东西：

1. **可审查**：老板（或另一个 Agent）能先看计划、再批准执行。
2. **可观察**：`progress()` 一眼看出做到第几步、卡在哪一步。
3. **可恢复**：状态是 `done/failed` 存着的，断了能接着跑（这正是第 12 章 Checkpoint 的地基）。

---

## 3、内核：harness/planning.py（第八块砖）

### 3.1 Plan / PlanStep —— 计划状态机

```python
@dataclass
class PlanStep:
    description: str
    status: str = "pending"    # pending → in_progress → done | failed
    result: str = ""
```

`Plan` 提供 `next_action()`（执行指针）、`mark_done/mark_failed`（推进）、`progress()`（打钩）、`is_complete()`。

### 3.2 make_plan —— 复用自己的第 07 章

```python
plan = make_plan(llm, "计划一次日本三日游", max_steps=5)
# 内部：structured_chat(llm, messages, PlanModel)
# PlanModel(steps: [str, ...])  → 程序能接住的步骤清单
```

这里刻意**复用第 07 章**：让 LLM 输出 `{"steps": [...]}` 这种结构，而不是「好的，建议步骤如下：1.…」这段要正则硬抠的散文。第七章下的功夫，第十章直接吃红利。`llm` 可换成 `FakePlanner`，测试无需 API。

### 3.3 execute_plan —— 逐步执行 + 失败即停

```python
results = execute_plan(plan, executor)   # executor(步骤描述, 序号) -> str
```

每步置 `in_progress`，成功 `done`、失败 `failed` **并立即停**。「失败即停」是有意的：计划中途断了不该硬往下跑——至于该怎么补偿（重试 / 反思 / 重规划），是第 11 章的戏，这里先把「停止」这一刀立住。完整实现见 [harness/planning.py](harness/planning.py)。

> 🧱 第八块砖落位：到这里，Agent 已经「会调用、有记忆、能循环、扛得住、说人话、懂治理、记得住、**拆得动**」——进入阶段四 State 层，让长任务（多步计划、中途失败也能活下来）有了可靠地基。

---

## 4、串联：Planning 与前面每一章

- **05**：`AgentLoop.run`（ReAct）没动；P&E 是它的「计划显式化」姊妹，不是取代。
- **07**：`make_plan` 直接吃 `structured_chat` 的红利。
- **09**：记忆让 Agent「记得住」，Planning 让 Agent「拆得动」——记忆是过去，计划是未来。
- **11/12**：`execute_plan` 的失败即停 → 第 11 章失败策略；`Plan` 的 `done/failed` 状态 → 第 12 章序列化断点续跑的地基。

---

## 5、运行本章案例

demo ①–④ 无需 `.env`，⑤ 需要（配置见 [第 01 章环境准备](01-LLM调用与环境准备.md#3、环境准备)）：

```bash
python examples/10_planning.py
```

预期输出（①–④ 是确定性的）：

```
① Plan：把「计划」变成可推进、可观察的状态
  [ ] 查天气
  [ ] 订酒店
  [ ] 买票
  [ ] 写行程表
  执行指针 next_action → '查天气'
  [x] 查天气
  是否全部完成：False

② make_plan：复用结构化输出，把目标拆成步骤清单
  目标：计划一次日本三日游
    第1步  查目的地天气
    第2步  订酒店
    …

③ execute_plan：逐步执行；第 3 步失败 → 立即停
  ✅ [0] 查天气 → 完成：查天气
  ✅ [1] 订酒店 → 完成：订酒店
  ❌ [2] 买票 → 买票接口超时了（模拟第 3 步失败）
  [!] 买票
  （失败即停是刻意的——怎么补偿是第 11 章）

④ ReAct vs Plan-and-Execute …
  ReAct：think → 调一个工具 → observe → 再 think → … 每轮只决定「下一步」
  Plan-and-Execute：make_plan 先出步骤清单 → execute_plan 逐步打钩

⑤ 真实 LLM：把目标拆成步骤清单
  目标：写一篇介绍 Agent 的公众号推送并发布
    第1步  …（真实模型生成，措辞不同）
```

> ⚠️ demo⑤ 的步骤清单由真实模型生成，内容不同——**重要的是形状**：一份「能照着逐条做」的步骤清单，而非一段散文。

---

## 6、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| `make_plan` 返回的步骤是空清单 | 模型没理解「输出 steps 数组」 | 在 `hint=` 里给一个示例 steps |
| 计划执行到一半停了 | `execute_plan` 失败即停（有意） | 第 11 章谈重试/反思；不想停就改 executor 吞异常 |
| 计划明显不合理 | 过度信任一次规划，没审查 | 先 `print(plan.progress())` 给人/上层看，批准再执行 |
| 想「分步执行每步还要再动脑」 | P&E 的步骤太粗 | 每步内部再跑小 ReAct（混用，见 §1） |
| `structured_chat` 报字段校验失败 | 模型输出非 `{"steps":[...]}` | 看返回的错误信息，模型会自动自纠；仍失败用真实模型 |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 7、本章小结与下一章

✅ 你现在已经能：

- 说清 ReAct（边想边做）与 Plan-and-Execute（先列清单再执行）的本质区别与取舍
- 用 `Plan`/`PlanStep` 把计划变成可推进、可观察、可审查的状态机
- 用 `make_plan` 复用结构化输出，让 LLM 吐程序能接住的步骤清单
- 用 `execute_plan` 逐步执行，并理解「失败即停」的用意
- 知道「计划越好 P&E 越省、计划越可能错越该回 ReAct」这个判断

➡️ 下一章 [**11 失败策略与反思 →**](11-失败策略与反思.md)（阶段四）：本章在失败时「叫停」了，下一章回答「然后呢」——**Self-Reflection、失败重试**：把失败信息回喂给模型，让它反思、重规划、再试（作为失败策略，不单独成主线范式）。可回[教程目录大纲](教程目录大纲.md)看全局。