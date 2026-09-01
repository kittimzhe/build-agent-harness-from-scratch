# 08 - Context 治理

> 📌 **第 8 章 · 阶段三 Context 层** · [← 返回目录大纲](教程目录大纲.md) · [上一章 07 结构化输出与 Schema 设计 →](07-结构化输出与Schema设计.md) · 下一章 09 记忆体系（规划中）

---

**本章课程目标：**

- 回到第 02 章看清那三根刺：上下文**越聊越大**（每轮 token 线性叠加）、**越聊越贵**、**越聊越失焦**（`lost in the middle`——塞进上下文的中段利用率最低）。
- 掌握三条治理路线：**压缩**（把旧历史压成摘要）、**取舍**（按预算挑 tokens）、**按需读取**（上下文只放「目录」，需要时再拉全文）。
- 建立决策直觉：**什么时候压缩、什么时候只存引用按需读**——这是 Context Engineering 的核心判断题。
- 还掉第 02 章的一笔债：`truncate` 按条数裁、奇数条会让历史以 `assistant` 开头——本章统一改成**按轮成对裁**。
- 落地第六块砖：`harness/context.py`（`estimate_tokens` / `keep_last_turns` / `compact` / `select_by_budget` / `ReferenceLibrary`）。

**学习建议：** demo ①–④ 是纯治理层，**不需要 API Key**，且确定性输出；⑤ 才走真实 LLM 压缩。本章的「治理三件套」和 06 的「容错三件套」一样，先把确定性的数据结构看明白，再谈真实调用。

---

## 1、回到第 02 章：那三根刺

第 02 章我们讲了「状态只有一份 `session.messages`」，也埋了三根刺没拔：

**① 越聊越大**：每问一轮，历史就多 `user` + `assistant` 两条；第 N 轮的 prompt_tokens ≈ 前 N-1 轮的总和。这是线性累积，不是错觉。

**② 越聊越贵**：因为 ①，每一轮都比上一轮更烧钱。聊一百轮之后，你大部分钱花在「重发自己说过的话」上。

**③ 越聊越失焦**：研究发现（`Lost in the Middle`）长上下文中，模型对**开头和结尾**记得牢，对**中间**的利用率断崖式下降。所以「全塞进去」不是中性的——塞得越多，中间越糊，模型反而越容易答偏。

第 02 章的 `truncate(keep_last_n)` 是治理第一刀：**一刀切掉旧的**。它能止血，代价是「忘事」（模型真的会忘记被截掉的内容）。本章要做的，是比「一刀切」更聪明的三招。

| 本教程 | 工程上对应 |
| --- | --- |
| `compact`（摘要压缩） | LangChain `ConversationSummaryMemory`；各种「摘要记忆」 |
| `select_by_budget`（预算取舍） | token 预算管理；上下文选择器 |
| `ReferenceLibrary`（按需读取） | RAG / 工具式检索的最简雏形 |

---

## 2、三条治理路线，一张决策表

| 路线 | 干什么 | 代价 | 什么时候用 |
| --- | --- | --- | --- |
| **压缩** | 旧历史 → 摘要，留语义丢废话 | 一次摘要调用的 token + 延迟，且会丢细节 | 历史长、后续还要「记得来龙去脉」 |
| **取舍** | 按预算只放「最有用的 tokens」 | 丢掉的信息找不回 | 有硬性 token 预算 / 只关心最近 |
| **按需读取** | 上下文放「目录」，需要时拉全文 | 多一次拉取的往返 | 内容大而冷、只偶尔用到一次 |

一个先记住的判断题：

> **热而短、反复用的内容 → 压进上下文；大而冷、偶尔用的内容 → 只存引用按需读。**
> 反了会怎样？把整本手册塞进上下文，每轮都为它付费，还稀释了注意力；把「当前正在纠结的决定」只存引用，模型每次都得重新拉一遍，又慢又脱节。

---

## 3、内核：harness/context.py（第六块砖）

全部是「接收 messages → 返回新 messages」的纯函数，不依赖 `ChatSession`，也不改任何已有签名。

### 3.1 estimate_tokens —— 先学会「量」

治理的前提是**量得出**。没有预算意识，一切「省 token」都是空话：

```python
def estimate_tokens(messages):
    # 中文 1 字 ≈ 1 token，其余 4 字符 ≈ 1 token（教学估算）
    ...
```

> 教学用估算；工程上应接真实 tokenizer（`tiktoken`）或直接用 API 返回的 `usage`。本章用它只求「相对大小」——哪段长、超没超预算。

### 3.2 keep_last_turns —— 先修好那把刀

`truncate` 按「条数」裁，`keep_last_turns` 按「轮」裁，且**保证历史以 `user` 开头**（按轮成对）：

```python
def keep_last_turns(messages, turns):
    system = [m for m in messages if m["role"] == "system"]
    rest = [m for m in messages if m["role"] != "system"]
    # 按 user 把 rest 切成轮，保留最后 turns 轮
    ...
    return system + kept
```

### 3.3 summarize / compact —— 压缩

```python
summary = summarize(llm, old_messages)          # LLM 把旧历史压成一段摘要
slim = compact(llm, messages, keep_last_turns_n=2)
# → system + 【前文摘要】+ 最近 2 轮原文
```

`compact` 的黄金结构：**旧历史只留一段摘要（5% 的 token 承载 80% 的语义），最近 N 轮原样保留**。为什么最近 N 轮不也压掉？因为「最近」承载着当前任务的直接脉络——刚问的、刚决定的，正是下一步要接着用的。

### 3.4 select_by_budget —— 取舍

```python
slim = select_by_budget(messages, max_tokens=600)
# 从最新往旧塞，直到预算满；至少保留最新一条；按轮成对
```

朴素版以「越新越相关」作相关性代理。真正的打分（向量相似度 / 关键词）是第 09 章记忆体系的戏。

### 3.5 ReferenceLibrary —— 按需读取

```python
lib = ReferenceLibrary({"ref-1": "很长很长的原文……"})
lib.catalog()        # 进上下文的是「目录」（几 token）
lib.fetch("ref-1")   # 需要时才拉全文
```

上下文里放**目录**（标题 + 一句摘要），模型需要详情时再 `fetch`。这就是 RAG 的最小雏形——第 09 章会把这份「目录」长成可检索的索引。

> 🧱 第六块砖落位：`LLMClient`（调用）+ `ChatSession`（状态）+ `AgentLoop`（循环）+ `tools`（容错）+ `schema`（结构化输出）+ `context`（治理）。到这里，你的 Agent 已经「会调用、有记忆、能循环、扛得住、说人话、还懂得省」。完整实现见 [harness/context.py](harness/context.py)。

---

## 4、还第 02 章的债：truncate 按轮成对裁

第 02 章的 `truncate(keep_last_n)` 按**条数**切。`keep_last_n=3` 时可能切成 `[assistant, user, assistant]`——**历史以 `assistant` 开头**，部分提供商会因角色顺序报错。

本章两个动作把它补上：

1. `ChatSession.truncate` 加了收尾：切完若首条不是 `user`（是 `assistant`，说明从一轮中间切开），就再往下丢到 `user` 为止。**偶数 N 行为完全不变**（2→2、6→6），只是奇数 N 不再留下「半轮」。
2. 新增 `keep_last_turns` 作为「按轮」这一正确姿势的显式原语，治理函数一律用它。

> 这也示范了内核的迭代纪律：**旧的 `truncate(6)` 用法一行不改还能跑，只是把之前会踩雷的边角加固了。**

---

## 5、决策框架：压缩 vs 取舍 vs 按需读取

把三招串成一个「问三句再动手」的框架：

1. **有没有硬预算？** 有 → 先 `select_by_budget` 兜住上限。
2. **旧内容后面还要不要记得细节？** 要（比如「用户太大纲还要接着聊」）→ `compact` 留摘要；不记得也无妨 → 直接 `keep_last_turns` 丢掉最旧的。
3. **那块内容是不是「大而冷、偶尔用」？** 是 → 别塞进上下文，存 `ReferenceLibrary` 的引用按需 `fetch`。

记住那个判断题（第 2 节）：**热而短反复用 → 压进上下文；大而冷偶尔用 → 只存引用**。这一句话就是 Context Engineering 的核心。

---

## 6、运行本章案例

demo ①–④ 纯治理层，**无需 `.env`**；demo ⑤ 需要（配置见 [第 01 章环境准备](01-LLM调用与环境准备.md#3、环境准备)）。

```bash
python examples/08_context_governance.py
```

预期输出（①–④ 是确定性的）：

```
① estimate_tokens + keep_last_turns：预算估算、按轮成对裁
  全程 11 条消息 ≈ 147 tokens
  keep_last_turns(2) → ['system', 'user', 'assistant', 'user', 'assistant']
  旧版『按条数裁 3 条』会以 assistant 开头（半轮）→ 角色顺序报错风险

② select_by_budget：预算内挑最有用的 tokens
  压缩前 147 tokens → 压缩后 33 tokens
  保留条数：3 / 11，首条角色：system

③ compact：把 80% 的内容压成 5% 的 token
  [system]   你是旅行规划助手
  [user]     【前文摘要】用户计划去日本玩5天，预算1万……
  [user]     最后问一句，现金要换多少？
  [assistant] 建议换 3000 元等值日元，其余刷卡。
  11 条消息 → 6 条（摘要 1 条 + 最近 2 轮原文）

④ 按需读取：上下文放『目录』，需要时才拉全文
  目录占 token：156
  拉全文 ref-1（270 字符）才进上下文；fetch 调用次数：1

⑤ 真实 LLM：把一段长对话压成摘要
  原始：11 条 ≈ 147 tokens
  压缩后：~3 条（system + 摘要 + 最近 1 轮原文）
  摘要：用户计划去日本玩5天……
```

> ⚠️ demo⑤ 的摘要文字由真实模型生成，措辞和上面不同——**重要的是结构**：`system + 一条【前文摘要】+ 最近 1 轮原文`，token 数明显下降。token 数这里用估算函数，同一份输入输出确定，但换模型不代表真实 billing。

---

## 7、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| 上下文越来越贵 | 没做治理，或只靠「聊完再说」 | 每轮后判断是否要 `compact` / `select_by_budget` |
| 模型「忘了」重要决定 | `truncate` / `keep_last_turns` 把关键信息裁掉了 | 关键信息落进摘要（`compact`）或存引用 |
| 报「角色顺序」错 | 历史以 `assistant` 开头（半轮） | 用 `keep_last_turns` / 加固后的 `truncate`，保证从 `user` 开始 |
| 摘要越压越丢关键细节 | 摘要指令没强调「保留决定/未完成事项」 | 用 `summarize(instruction=...)` 定制指令 |
| token 估算与实际账单对不上 | `estimate_tokens` 是粗略估算 | 换真实 tokenizer；只看「相对大小」，别当记账 |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 8、本章小结与下一章

✅ 你现在已经能：

- 说清第 02 章埋的三根刺：越聊越大、越聊越贵、越聊越失焦（lost in the middle）
- 用三招治理上下文：`compact`（压缩）、`select_by_budget`（取舍）、`ReferenceLibrary`（按需读取）
- 用一个判断题做决策：热而短反复用 → 压进上下文；大而冷偶尔用 → 只存引用
- 按轮成对裁，根治「历史以 assistant 开头」的角色顺序隐患
- 量得出 token 预算（`estimate_tokens`），才有资格谈「省」

➡️ 下一章 **09 记忆体系**（阶段三收官）：本章的「目录 + fetch」只是最小雏形，下一章把它长成真正的记忆——**短期记忆（会话内）vs 长期记忆（跨会话/文件）vs 向量记忆（语义检索）**，以及那道老题：**RAG 与 Memory 的边界在哪**。可回[教程目录大纲](教程目录大纲.md)看全局。