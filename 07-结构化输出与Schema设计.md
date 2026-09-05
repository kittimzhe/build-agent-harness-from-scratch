# 07 - 结构化输出与 Schema 设计

> 📌 **第 7 章 · 阶段二 Tool 层** · [← 返回目录大纲](教程目录大纲.md) · [上一章 06 工具集合与容错 →](06-工具集合与容错.md) · [下一章 08 Context 治理 →](08-Context治理.md)

---

**本章课程目标：**

- 看清一个痛点：模型回答是一段**自由文本**，你想拿到 `label`、`score`，却只能靠正则去抠——格式一漂移，下游全崩。
- 掌握结构化输出的三层武器：**JSON Mode（保证是合法 JSON）→ Pydantic 校验（保证字段类型/必填/约束对）→ 自纠重试（校验失败时把错误回喂模型，让它自己修）**。
- 理解 schema 的「一鱼两吃」：第 05 章用 JSON Schema 约束**工具入参**，本章用它约束**模型输出**——同一套 schema 思想，锁住「模型说的」和「模型要的」。
- 落地第五块砖：`harness/schema.py`（`extract_json` / `strict_validate` / `structured_chat`）。

**学习建议：** demo ①–③ 是纯解析/校验层，**不需要 API Key**，且确定性输出；④ 才走真实 LLM。先跑 ①–③ 建立「校验到底拦什么」的直觉，再跑 ④ 看真实模型被关进类型系统。

---

## 1、为什么模型输出需要「结构」

到目前为止，`LLMClient.chat()` 返回的 `content` 是一段字符串。字符串本身没问题——问题是**下游怎么消费它**。

假如你要做一个「客服工单自动分类」：让模型判断一封工单是 `退款 / 咨询 / 投诉`，再决定路由给谁。如果只靠自然语言：

```python
result = llm.chat([{"role": "user", "content": "这封工单属于哪类？只回答：退款/咨询/投诉"}])
route_to(result.content)
```

模型某天输出「这是投诉类工单」，你 `if "投诉" in content` 还能兜住；哪天它说「我认为属于投诉」，你的正则会漏；哪天它夹带一句吹捧，你就得更啰嗦地兜——**你在用正则和运气跟一个概率模型对赌**。

结构化输出的思路正好反过来：**让模型输出一个「形状是预先声明的」数据结构**，再交给类型系统（Pydantic）去把关。拦得住就是合法数据，拦不住就拒绝并让模型重来。

```python
class Ticket(BaseModel):
    category: Literal["refund", "consult", "complaint"]
    urgency: int = Field(ge=1, le=5)
    keywords: list[str]
```

> 一句话：**自由文本留给人类看，结构留给程序用**。Agent 的每一步「思考 → 决策 → 行动」，只要要喂给程序，就该是可解析、可校验的。

| 本教程 | 框架里对应的东西 |
| --- | --- |
| `strict_validate` + Pydantic 模型 | LangChain `with_structured_output(pydantic_model)`；OpenAI `response_format=json_schema` |
| `structured_chat` + 自纠重试 | 框架的「解析失败重试」（output parser auto-fix） |
| `extract_json` | LangChain 各种 output parser 的「剥围栏 / 抠 JSON」那部分 |

---

## 2、三层武器：JSON Mode → Pydantic → 自纠

### 2.1 JSON Mode（第一层：保证「是 JSON」）

给请求加 `response_format={"type": "json_object"}`，模型就**保证输出合法 JSON**（不是 JSON 会报错或空转）。但注意——它只保证「是合法 JSON」，**不保证字段按你想要的来**：

```json
{"分类": "投诉", "紧急度": "高"}   // 合法 JSON，但字段名、类型全不对
```

所以 JSON Mode 是「把格式这道门关上」，字段形状还得靠下一层。

> 另有一条更硬的路径：原生 **structured output**（`response_format={"type": "json_schema", ...}`，把 schema 直接交给 API，锁死结构）。OpenAI / DeepSeek 支持，但各提供商支持程度不一，本章内核用「JSON Mode + schema 提示词」这种**跨提供商通用**的做法，native 那条在正文里点一句即可。

### 2.2 Pydantic 校验（第二层：保证「字段对」）

Pydantic 用 Python 类型注解声明数据形状，`model_validate()` 做校验：

- `label: Literal["refund", "consult", "complaint"]` → 枚举约束
- `urgency: int = Field(ge=1, le=5)` → 数值区间
- `keywords: list[str]` → 类型 + 必填

校验失败的细节（哪个字段、哪条约束没满足）都会被 Pydantic 逐条列出来——这些信息正好能喂回给模型（见 2.3）。

### 2.3 自纠重试（第三层：保证「最终可用」）

解析失败时，别急着让整个任务失败——**把错误回喂给模型，让它自己改**：

```
你上一次的输出没有通过校验，错误如下：
字段校验失败：score ... 大于最大允许值 1
请修正后重新输出，只输出符合要求的 JSON，不要解释。
```

这和第 06 章「工具失败回喂模型」是同一个哲学，但用在了**输出侧**：模型看到具体错误，通常能一次改对。三次兜底（JSON Mode 兜格式、Pydantic 兜字段、自纠兜最终成功率）叠加，让「拿回可用结构」从靠运气变成工程保证。

---

## 3、内核：harness/schema.py（第五块砖）

### 3.1 extract_json —— 抠出 JSON

模型输出常带 ```json``` 代码围栏、或「好的，结果如下」这类前后缀：

```python
def extract_json(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise StructuredOutputError(f"模型输出里找不到 JSON：{text[:120]!r}")
    return text[start:end + 1]
```

先剥围栏，再取最外层花括号——两个动作就兜住了 90% 的格式漂移。

### 3.2 strict_validate —— 解析 + 校验一条龙

```python
def strict_validate(model_cls, text):
    data = json.loads(extract_json(text))       # 先 JSON 解析
    return model_cls.model_validate(data)        # 再 Pydantic 校验
```

两步各自失败，都转成统一的 `StructuredOutputError`，带上**可回喂给模型的错误文本**。

### 3.3 structured_chat —— 签名外的包装

```python
def structured_chat(llm, messages, model_cls, max_retries=2, json_mode=True):
    ...  # 把 model_cls.model_json_schema() 塞进 system，声明输出形状
    for attempt in range(max_retries + 1):
        result = llm.chat(history, response_format={"type": "json_object"})
        try:
            return strict_validate(model_cls, result.content or "")
        except StructuredOutputError as e:
            history.append({"role": "user", "content": f"你上一次输出没通过校验：{e}\n请修正后重新输出 JSON"})
    raise StructuredOutputError(...)
```

注意它**没有动 `chat()` 的签名**——结构化输出是 `chat` 之上的一层包装，内核仍然是「只加能力」。完整实现见 [harness/schema.py](harness/schema.py)。

> 🧱 第五块砖落位：`LLMClient`（调用）+ `ChatSession`（状态）+ `AgentLoop`（循环）+ `tools`（容错）+ `schema`（结构化输出）。至此，模型的**进**（工具入参）和**出**（结构化回答）都被 schema 锁住了——Agent 的每一步都能被程序可靠地消费。

---

## 4、schema 的「一鱼两吃」：入参与输出是同一个思想

把第 05 章和第 07 章放一起看，你会发现它们是同一件事的两面：

| | 第 05 章 | 第 07 章 |
| --- | --- | --- |
| **约束什么** | 工具要传的**入参** | 模型要给的**输出** |
| **schema 在哪** | `Tool.parameters` | Pydantic 模型 / `model_json_schema()` |
| **校验在哪** | 解析 `arguments` 字符串、`agentloop` 执行前 | `strict_validate` 拿到答案后 |
| **失败怎么办** | 回喂模型改参数（`role="tool"` 报错） | 回喂模型改输出（自纠重试） |

这条线（怎么写出模型「看得懂、不误用」的参数描述、什么时候该用少数几个大字段而不是一堆小字段）在第 05 章的工具循环里边用边练——本章先建立「入出都要锁」的直觉即可。

---

## 5、运行本章案例

demo ①–③ 纯解析/校验层，**无需 `.env`**；demo ④ 需要（配置见 [第 01 章环境准备](01-LLM调用与环境准备.md#3、环境准备)）。

```bash
python examples/07_structured_output.py
```

预期输出（①–③ 是确定性的）：

```
① extract_json：从不干净的输出里抠 JSON
  '{"a": 1}'                          → {"a": 1}
  '```json\n{"a": 1}\n```'            → {"a": 1}
  '好的，结果如下：{"a": 1} 希望有帮助'    → {"a": 1}
  ...

② strict_validate：Pydantic 校验三类失败
  ❌ label 不在枚举里 → 1 validation error ... 'happy' is not in ...
  ❌ score 越界（0-1）→ ... Less than or equal to 1
  ❌ 缺少 keywords 必填字段 → ... Field required
  ✅ 合法输入 → {'label': 'positive', 'score': 0.85, 'keywords': ['周到']}

③ 自纠重试：解析失败 → 错误回喂 → 模型改正
  最终拿回：{'label': 'positive', 'score': 0.85, 'keywords': ['好']}
  说明：第 1 次输出被 Pydantic 拒了，错误作为 user 消息回喂，第 2 次才通过

④ 真实 LLM：情绪分析，返回已验证的 Pydantic 对象
  输入：等了四十分钟，结果待办还办不了，太气人了
  分析：{'label': 'negative', 'score': 0.92, 'keywords': [...]}
  类型校验通过：label 必为枚举、score 必在 [0,1]
```

> ⚠️ demo ④ 依赖模型，具体分数/关键词会和上面不同——这不重要，**重要的是它必须是一个通过了 Pydantic 校验的 `Sentiment` 对象**（label 是枚举、score 在 [0,1] 内）。如果它第一次给错被拒、第二次才过，你还能看到自纠发生在真实调用里。

---

## 6、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| `StructuredOutputError: 模型输出里找不到 JSON` | 模型没按 JSON Mode 输出，或早于 2024 的模型不支持 `response_format` | 把「只输出 JSON」写进 prompt；换支持 JSON Mode 的模型 |
| `字段校验失败：... str type expected` | 模型把一个字段类型写错了 | 靠自纠重试；或在 prompt 里给一个完整示例（few-shot） |
| 重试两轮还是不过 | 模型没理解 schema，或 schema 本身自相矛盾 | 简化 schema；把示例写进 prompt；`max_retries` 调大 |
| 想硬锁死结构 | JSON Mode 还允许「合法但字段不同」的 JSON | 换原生 `response_format={"type":"json_schema"}`（见 §2.1） |
| Pydantic 导入失败 | 没装依赖 | `pip install pydantic`（已在 requirements.txt，`pip install -r requirements.txt` 一并装） |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 7、本章小结与下一章

✅ 你现在已经能：

- 说清「模型输出为什么需要结构」：自由文本给人类，结构给程序
- 分三层做结构化输出：JSON Mode（兜格式）→ Pydantic（兜字段）→ 自纠重试（兜成功率）
- 用 `extract_json` / `strict_validate` / `structured_chat` 拿回强类型对象
- 理解 schema「一鱼两吃」：约束工具入参（05）与约束模型输出（07）是同一思想

➡️ 下一章 [**08 Context 治理 →**](08-Context治理.md)（阶段三）：工具有了、输出稳了，下一个瓶颈回到第 02 章埋下的那根刺——**上下文会越聊越大、越聊越贵、越聊越「失焦」**。压缩、取舍、按需读取，就是下一章要拆的东西。可回[教程目录大纲](教程目录大纲.md)看全局。