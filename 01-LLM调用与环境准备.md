# 01 - LLM 调用与环境准备

> 📌 **第 1 章 · 阶段一 Prompt 层** · [← 返回目录大纲](教程目录大纲.md) · [上一章 无](README.md) · [下一章 02 消息状态与上下文窗口 →](02-消息状态与上下文窗口.md)

---

**本章课程目标：**

- 从「知道 Agent 是什么」走到「**亲手跑通第一次 LLM 调用**」，完成环境准备到 HelloWorld 的闭环。
- 理解接入大模型最重要的 **调用三件套**：**API Key、模型名、Base URL**。学会它，DeepSeek、通义千问、OpenAI、Ollama 都是同一套代码。
- 把一次裸调用封装成最小的 `LLMClient`，为后面所有章节（ReAct、RAG、Runtime）打地基——这就是我们「从零手写 Harness」的第一块砖。想看全局路线，见[教程目录大纲](教程目录大纲.md)。
- 会运行并理解本章全部案例：**环境检查、同步调用、流式输出、客户端封装**。

**学习建议：** 这一章的目标很朴素：先让一次模型调用真的跑起来。先把 `.env`、依赖、模型名确认好，再看代码结构；第一次成功后，再理解「为什么所有兼容 OpenAI 协议的模型都长一个样」。遇到报错先翻[新手入门与常见问题](新手入门与常见问题.md)。

**官方文档与资源**：详见 [工具导航与参考资料索引](工具导航与参考资料索引.md)。

---

## 1、为什么这份教程不用现成框架

在动手之前，先把一个最关键的问题讲清楚：**我们为什么不直接用 LangChain / LangGraph？**

市面上大多数 Agent 教程的路径是：装 LangChain → 照着文档写 `agent.invoke(...)` → 跑通了 → 但你不知道它背后发生了什么。这种「速成」能让你快速做出 demo，却会在两个时刻崩塌：

1. **出 bug 的时候**：工具调用没按预期走、上下文爆了、循环停不下来——你看不到中间过程，因为框架把它们藏起来了。
2. **面试的时候**：面试官问「你的 Agent 循环是怎么终止的」「上下文怎么治理的」，你只能说「LangChain 帮我处理了」。

行业正在发生一个重要变化（详见[面试题库 · 前沿主线](面试题库.md)）：**Agent 的工程重心已经从 Prompt 迁移到 context、harness、eval、protocol、runtime。** 也就是说，真正值钱的能力不是「会调框架」，而是「看懂 LLM 在一个什么脚手架（Harness）里工作」。

> **Harness**（脚手架）：包裹 LLM 的运行时——状态管理、工具访问、checkpoint 恢复、trace 日志、权限审批、终止条件。LangChain/LangGraph 本质上就是一个 Harness。

所以本教程的定位是：**不用任何 Agent 框架，用纯 Python + LLM SDK，一步步把一个 Harness 从零搓出来。** 每一章都是在 Harness 上加一层能力：

```
第01章 LLMClient  →  第05章 ReAct循环  →  第09章 记忆  →  第12章 Checkpoint
                                          ↓
              第13章 把这些封装成一个 mini Agent Runtime
```

读完你会彻底看懂：那些成熟框架，到底替你做了什么、什么时候该自己写、什么时候该用框架。

> 💡 **一句话记住本教程的主线**：不是「学怎么用 LangChain」，而是「从零手写一个 mini LangGraph，从而看懂所有框架」。

---

## 2、调用三件套：API Key、模型名、Base URL

这是本章最该带走的知识点。**几乎所有「兼容 OpenAI 协议」的模型提供商，调用方式都是同一套，只差三个值：**

| 三件套 | 是什么 | 在哪拿 |
| --- | --- | --- |
| **API Key** | 你的身份凭证，`sk-xxx` | 提供商控制台申请 |
| **模型名** | 调哪个模型，如 `deepseek-chat` | 提供商文档 |
| **Base URL** | API 入口地址，如 `https://api.deepseek.com` | 提供商文档 |

本教程默认用 **DeepSeek**（国内便宜、稳定、原生兼容 OpenAI 协议）。但你真正要学会的是「怎么用 OpenAI SDK 接任意模型」，而不是只会某一个平台。

### 2.1 各平台的三个值对照

| 提供商 | Base URL | 模型名（示例） | 说明 |
| --- | --- | --- | --- |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` | 推荐，便宜稳定 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | 兼容模式入口 |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | 需能访问 |
| Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` | 本地，无需 Key |

> 注意：通义千问、Ollama 的 Base URL 末尾有 `/v1`，DeepSeek 没有（SDK 会自己补）。这坑踩过的人都懂。

### 2.2 为什么是「同一套代码」

因为 OpenAI 的 Python SDK 已经成了事实标准，DeepSeek、通义、Ollama 都主动兼容它。你只需要换三个值：

```python
from openai import OpenAI

client = OpenAI(
    api_key="你的 API Key",        # 换成你的
    base_url="https://api.deepseek.com",  # 换成你的
)
resp = client.chat.completions.create(
    model="deepseek-chat",          # 换成你的模型名
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)
```

把 `api_key` / `base_url` / `model` 换成通义千问的值，代码一行不用改就能跑。这就是「调用三件套」的威力。

---

## 3、环境准备

### 3.1 Python 版本

- **推荐**：Python **3.10**（支持 3.10–3.13，不建议 3.14）
- 本教程 `requirements.txt` 已写好依赖。

### 3.2 创建虚拟环境并装依赖

```bash
python3.10 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows CMD
pip install -r requirements.txt
```

### 3.3 配置 API Key

把根目录 `.env-example` 复制为 `.env`，填入你的 DeepSeek Key：

```bash
cp .env-example .env
```

`.env` 里关键三行：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### 3.4 运行约定（很重要）

> ⚠️ **必须在项目根目录运行案例**，否则读不到根目录的 `.env`，会出现 API Key 为空、401、403 等报错。

正确写法：

```bash
python 案例与源码-1-Prompt层/01-HelloLLM.py
```

---

## 4、第一次调用：同步 + 流式

### 4.1 同步调用

最朴素的一次调用，等模型把整段回答生成完再返回：

```python
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()  # 从 .env 读取环境变量

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)

resp = client.chat.completions.create(
    model=os.getenv("DEEPSEEK_MODEL"),
    messages=[{"role": "user", "content": "用一句话解释什么是 Agent Harness"}],
)
print(resp.choices[0].message.content)
```

### 4.2 流式输出

Agent 在实际产品里几乎都要流式——边生成边返回，用户体验好很多，长任务也不会卡死。把 `stream=True` 打开即可：

```python
stream = client.chat.completions.create(
    model=os.getenv("DEEPSEEK_MODEL"),
    messages=[{"role": "user", "content": "用一句话解释什么是 Agent Harness"}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
```

> 注意 `delta.content` 可能为 `None`（首块只有 role），所以用 `or ""` 兜底。这是流式调用最常见的第一个坑。

### 4.3 同步 vs 流式怎么选

| 场景 | 选哪个 | 原因 |
| --- | --- | --- |
| 后台批处理、一次性问答 | 同步 | 实现简单 |
| 面向用户的对话、Agent 中间步骤 | 流式 | 体验好、可提前判断 |
| Agent 循环里调工具前的「思考」 | 流式 | 方便观察、可中断 |

> 💡 后面 ReAct 循环里，我们会用同步调用拿结构化结果，但会保留流式能力——这是 Harness 该提供的选项。

---

## 5、封装 LLMClient：第一块 Harness 砖

裸调用写两次你就会嫌烦。更重要的是，后面十几章都要调模型，如果每次都写 `OpenAI(api_key=..., base_url=...)`，换一个模型要改十几个文件。

所以我们要把「调用三件套 + 环境变量」封装成一个最小的 `LLMClient`。**这就是我们手写 Harness 的第一块砖。**

### 5.1 设计要点

一个合格的 LLM 客户端封装，至少要解决三件事：

1. **配置集中**：从 `.env` 读 `LLM_PROVIDER`，自动选对应的 Key/URL/模型。换模型只改 `.env`，不改代码。
2. **统一接口**：对外只暴露 `chat(messages, stream=False)`，内部处理同步/流式差异。
3. **可扩展**：后面要加 token 计数、重试、trace——都得能挂进来。

### 5.2 实现

完整代码见 [llm_client.py](案例与源码-1-Prompt层/llm_client.py)（可本地运行，运行方式见[第 6 节](#6、运行本章案例)）。核心长这样：

```python
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# 提供商 → 配置的映射，换模型只改 .env
PROVIDERS = {
    "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"),
    "qwen":     ("DASHSCOPE_API_KEY", "QWEN_BASE_URL", "QWEN_MODEL"),
    "openai":   ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"),
    "ollama":   ("OLLAMA_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL"),
}

class LLMClient:
    def __init__(self, provider=None):
        provider = provider or os.getenv("LLM_PROVIDER", "deepseek")
        key_env, url_env, model_env = PROVIDERS[provider]
        self.model = os.getenv(model_env)
        self.client = OpenAI(
            api_key=os.getenv(key_env) or "ollama",  # ollama 不需要 key
            base_url=os.getenv(url_env),
        )

    def chat(self, messages, stream=False, **kwargs):
        """统一调用入口。messages 是 [{role, content}, ...] 列表。"""
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            **kwargs,
        )
```

### 5.3 用起来

```python
from llm_client import LLMClient

llm = LLMClient()  # 自动读 .env 里的 LLM_PROVIDER
resp = llm.chat([{"role": "user", "content": "你好"}])
print(resp.choices[0].message.content)
```

换通义千问？把 `.env` 里 `LLM_PROVIDER=qwen`，代码一行不改。

> 🧱 **这一步的意义**：你已经写出了 Harness 的第一块砖——一个统一的模型调用层。后面所有能力（ReAct、RAG、Memory、Checkpoint）都会建在它之上。等到第 13 章，你会看到它如何演变成一个完整的 Agent Runtime。

---

## 6、运行本章案例

确保你已完成[第 3 节环境准备](#3、环境准备)（装好依赖、填好 `.env`），然后在项目根目录运行：

```bash
# 必须在项目根目录
python 案例与源码-1-Prompt层/01-HelloLLM.py
```

预期输出（依次跑三个 demo）：

```
✅ 环境自检通过：provider=deepseek, key_env=DEEPSEEK_API_KEY
==================================================
① 同步调用
==================================================
Agent Harness 是包裹 LLM 的运行时脚手架……（模型完整回答）
==================================================
② 流式调用
==================================================
A-g-e-n-t- -H-a-r-n-e-s-s-…（逐字打印）
==================================================
③ 多轮对话（消息历史累积）
==================================================
用户：我叫小明
模型：你好小明！
用户：我叫什么名字？
模型：你叫小明呀。
```

> 💡 如果第三轮模型没记住名字，多半是 `.env` 没读到或上下文没累积——检查是否在根目录运行、是否激活了虚拟环境。

---

## 7、常见报错排查

| 报错 | 原因 | 解决 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'openai'` | 虚拟环境没激活或没装依赖 | `source .venv/bin/activate && pip install -r requirements.txt` |
| `AuthenticationError` / 401 / 403 | API Key 为空或错误 | 确认 `.env` 填了 Key，且在**根目录**运行（能读到 `.env`） |
| `NotFoundError` / 404 | Base URL 写错（比如通义忘了 `/v1`） | 对照 [2.1 各平台三个值](#21-各平台的三个值对照) 检查 |
| 连接超时 | 国内访问 OpenAI 需代理 | 改用 DeepSeek / 通义千问 |
| `delta.content` 报 `None` | 流式首块没有 content | 用 `delta.content or ""` 兜底 |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 8、本章小结与下一章

✅ 你现在已经能：
- 跑通第一次 LLM 调用（同步 + 流式）
- 说出调用三件套，理解为什么兼容 OpenAI 协议的模型都长一个样
- 把裸调用封装成可复用的 `LLMClient`（Harness 第一块砖）

➡️ 下一章 [02 消息状态与上下文窗口](02-消息状态与上下文窗口.md)，我们会在 `LLMClient` 上加第二块砖：**多轮对话与消息历史**。你会理解 Token 计数、上下文窗口、KV Cache，以及为什么「上下文不是静态输入，而是动态演化的状态」——这是从 Prompt 走向 Context Engineering 的起点。
