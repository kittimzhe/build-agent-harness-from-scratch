# 12 - Checkpoint 与状态恢复

> 📌 **第 12 章 · 阶段四 State 层（收官）** · [← 返回目录大纲](教程目录大纲.md) · [上一章 11 失败策略与反思 →](11-失败策略与反思.md) · 下一章 13 封装 Mini Agent Runtime（规划中）

---

**本章课程目标：**

- 说清**状态序列化**：把运行中的 `Plan`（第 10 章）变成能安全写盘、再还原的字典。
- 掌握**断点续跑**：进程崩了不可怕，从盘上读回状态接着做，重跑一切「还没 done」的步骤。
- 理解 **Durable Execution** 的核心三句话：状态是真源、SAVE 是常态、执行只是推进状态。
- 落地第十块砖：`harness/state.py`（`plan_to_dict` / `plan_from_dict` / `save_checkpoint` / `load_checkpoint` / `run_plan_with_checkpoint`）。

**学习建议：** 本章全部 demo **不需要 API Key**——序列化、落盘、恢复都是本地确定性操作。它是阶段四的收官：把前两章的 `Plan` 状态和反思轨迹，从「内存里的一次性」变成「磁盘上的可恢复」。

---

## 1、为什么状态要「能落地」

第 10 章的 `Plan` 有状态（每步 `done/failed`），第 11 章的反思有轨迹（`attempts`）——但都在**内存里**：进程被 kill、机器重启、代码抛个没接住的异常，全没。对一个要跑好多步的长任务，这是不可接受的。

所以第 12 章做一件很朴素、却最救命的事：**把状态变成字符串，写进文件。** 这就是「状态序列化」：

```python
plan_to_dict(plan)        # Plan 对象 → 可 JSON 的字典
save_checkpoint(plan)     # 字典 → checkpoint.json
load_checkpoint()         # checkpoint.json → 全新的 Plan 对象
```

> 一句话立住：**状态是唯一事实（Single Source of Truth），执行只是「推进状态 + 每一步立刻落盘」。** 进程是易失的，文件才是靠得住的。

---

## 2、断点续跑 vs 从头再跑

断点续跑的关键，不是「记住我做过啥」，而是**「哪些还没做完 = 不该重做」**：

| 步骤状态 | 恢复时 |
| --- | --- |
| `done` | 跳过（这是唯一的稳定边界） |
| `pending` | 重跑（还没开始） |
| `in_progress` | 重跑（崩溃时卡在中间，结果未知） |
| `failed` | 重跑（没 done 就是没做完） |

注意这和第 10 章 `execute_plan` 的差别：第 10 章 `failed` 被永久跳过（失败即停、你手动决定）；本章的 `run_plan_with_checkpoint` 把 `failed` 视作**「还没做完」**，恢复时重跑——这就是 Durable Execution 里的 **at-least-once** 语义：宁可多做一步，不可假装做过。

> at-least-once 的代价是「可能重复执行有副作用的一步」。所以落盘边界要刷得够勤：本框架在**每一步前后都 save**，把「重复」的窗口压到最小。

---

## 3、内核：harness/state.py（第十块砖）

### 3.1 序列化往返

```python
plan.mark_done(0, "拉了 1200 单")
d = plan_to_dict(plan)          # {"goal": ..., "steps": [{"description","status","result"}], "version": 1}
back = plan_from_dict(d)        # 还原出一个状态相同的 Plan
```

`version` 字段是给未来格式演进留的余地（`.v2` 的 checkpoint 能识别、能迁移）。

### 3.2 run_plan_with_checkpoint —— 每步都落盘

```python
run_plan_with_checkpoint(plan, executor, "checkpoint.json")
# 只跑 status != done 的步骤；每步：置 in_progress → save → 执行 → done/failed → save
# 失败：save 后把异常抛出去（本次执行停止），但进度已落盘，可随时恢复
```

完整实现见 [harness/state.py](harness/state.py)。

> 🧱 第十块砖落位，**阶段四 State 层收官**：`planning`（拆任务）+ `reflection`（救失败）+ `state`（保进度）三块砖，让长任务「拆得动、扛得住、丢不了」。下一步进入阶段五 Runtime 层，把这些能力封装成一个可复用的 mini runtime。

---

## 4、串联：Checkpoint 与前几章

- **09**：`FileMemory` 是「跨会话的事实」，`checkpoint` 是「单次长任务的进度」——一个横跨任务、一个纵贯单次任务的从头到尾。
- **10**：`Plan.steps` 的 `status` 是本章序列化的对象；`execute_plan`（无持久化、失败即停）vs `run_plan_with_checkpoint`（每步落盘、failed 重跑）。
- **11**：`ReflectionResult.attempts` 一样可以序列化——反思轨迹是「怎么救回来的」的证据（本题不展开，思路同 §3.1）。
- **14**：checkpoint 是「状态」的落盘，trace 是「过程」的落盘——前者为恢复，后者为排查回放。

---

## 5、运行本章案例

无需 `.env`：

```bash
python examples/12_checkpoint.py
```

预期输出（全部确定性）：

```
① 序列化往返：Plan ↔ dict ↔ Plan
  dict 里的 goal： 出周报
  往返后第 0 步状态： done | 结果：拉了 1200 单
  往返后第 1 步状态： in_progress

② checkpoint.json 长什么样
  {
    "version": 1,
    "goal": "出周报",
    "steps": [
      {"description": "拉订单数据", "status": "done", "result": "拉了 1200 单"},
      ...
    ]
  }

③ 断点续跑：进程崩了，从 checkpoint 恢复接着做
  第一次执行中断。落盘状态：
    [x] 拉订单数据
    [!] 算总额
    [ ] 画图
    [ ] 发邮件
  重启后 load_checkpoint 得到的状态：
    [x] 拉订单数据
    [!] 算总额
    …
  修复后恢复执行，最终：
    [x] 拉订单数据
    [x] 算总额
    [x] 画图
    [x] 发邮件
  全部完成：True（第 1 步 failed 被重跑成 done）

④ Durable Execution：状态是真源，执行只推进状态并每步落盘
  1. SAVE 是常态、不是事后…
  2. 只重跑「还没 done」的…
  3. 恢复 = 加载状态 + 继续推进…
```

> 看 demo③ 抓一个点：第一次执行在第 1 步「崩溃」前**已经把 `[x] 拉订单数据` 落盘了**，恢复后它不再重跑；而 `[!] 算总额` 因为「没 done」，恢复后被重跑成 done。这就是断点续跑的全部秘密。

---

## 6、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| 恢复后从第 0 步重新跑 | 没在每步后 `save` | 用 `run_plan_with_checkpoint`（每步前后都落盘） |
| 恢复后把已完成的又做一遍 | 没把 `done` 当跳过边界 | 恢复循环里只跳过 `status == done` |
| checkpoint 读不出来 | 反序列化格式对不上 | 看 `version` 字段，做迁移；别手改 JSON |
| 某步有副作用却重复执行了 | at-least-once 的固有代价 | 把落盘刷勤（本章已每步刷），副作用步做成幂等 |
| 想区分「崩溃卡住」和「失败」 | `in_progress` 和 `failed` 没分开用 | 崩溃前置 `in_progress`、执行后置 `done/failed`（本章已如此） |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 7、本章小结与下一章

✅ 你现在已经能：

- 用 `plan_to_dict` / `plan_from_dict` 做状态序列化往返
- 用 `save_checkpoint` / `load_checkpoint` 落盘与恢复
- 用 `run_plan_with_checkpoint` 做到每步落盘的断点续跑
- 说清 Durable Execution 三句话：状态是真源、SAVE 是常态、只重跑没 done 的
- 分清 at-least-once（本章）与「失败即停」（第 10 章）的取舍

➡️ 下一章 **13 封装 Mini Agent Runtime**（阶段五 Runtime 层开局）：现在内核有九块砖了，但每一块都得自己手动装配——下一步把它们封装成一个**状态机 + 事件循环**的 mini runtime，并对比 LangGraph / OpenAI Agents SDK，看看我们手写的东西在「什么位置」。可回[教程目录大纲](教程目录大纲.md)看全局。