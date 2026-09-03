<div align='center'>
  <h1>🛠️ 从零手写 Agent Harness：从 Prompt 到 Runtime</h1>
  <h4><b>build-agent-harness-from-scratch</b></h4>
  <p><em>不调框架、不抄概念，用纯 Python + LLM SDK 从零搓出一个能跑的 Agent Harness / Runtime，看懂 LangChain、LangGraph、OpenAI Agents SDK 到底替你做了什么</em></p>
</div>

<div align="center">

![Language](https://img.shields.io/badge/language-Chinese-2ea44f?style=flat)
![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)
![Status](https://img.shields.io/badge/status-持续更新中-orange?style=flat)
![Chapters](https://img.shields.io/badge/已发布-01·02·05·06·07·08·09·10·11·12·13-09f?style=flat)

> 📌 **当前进度**：已发布 `01`（LLM 调用）、`02`（消息状态）、`05`（工具循环）、`06`（工具容错）、`07`（结构化输出）、`08`（Context 治理）、`09`（记忆体系）、`10`（任务拆解与 Planning）、`11`（失败策略与反思）、`12`（Checkpoint 与状态恢复）、`13`（封装 Mini Agent Runtime）——「调用 → 状态 → 循环 → 容错 → 结构化 → 治理 → 记忆 → 规划 → 反思 → 保进度 → 封 runtime」主线十一连，阶段五 Runtime 层开局；其余章节规划中，侧边栏已标注，点开不会 404。

[快速开始](#-快速开始) • [教程大纲](教程目录大纲.md) • [面试题库](面试题库.md) • [常见问题](新手入门与常见问题.md) • [更新日志](教程更新日志.md)

</div>

---

## ✨ 这份教程在讲什么

> **一句话主线**：Prompt 仍然重要，但 2025–2026 真正拉开工程差距的重心，已经明显转向 **context、tooling、harness、eval、protocol 和 runtime**。

市面上 Agent 教程大多分两类：要么是「调 LangChain/LangGraph 的速成」，要么是「概念名词大集合」。本教程走第三条路 —— **不用任何现成 Agent 框架**，用纯 Python + OpenAI 兼容 SDK（DeepSeek / 通义千问 / Ollama），一步一步把一个 Agent 从「只会聊天」搓到「能调工具、有记忆、会规划、可恢复、可观测、可部署」。

读者跟着敲完代码，等于亲手实现了一个 **mini Agent Harness / Runtime**。最后一章我们会把它封装成一个可复用的内核，让你彻底看懂：那些成熟框架到底替你做了什么、什么时候该自己写、什么时候该用框架。

**这不是又一份「Agent 是什么」的概念贴，而是一条「从 Prompt 到 Runtime」的可执行工程主线。**

---

## 🧭 为什么是 Harness，不是又一个 Agent 框架

行业正在从「模型能力展示」转向「系统能力建设」：

| 能力层级 | 解决的问题 | 本教程对应阶段 |
| --- | --- | --- |
| **Prompt Engineering** | 怎么写出有效指令 | 阶段一：Prompt 层 |
| **Context Engineering** | 多轮中持续组织「最有用的那部分 tokens」 | 阶段三：Context 层 |
| **Harness Engineering** | LLM 在一个什么脚手架里工作：状态、checkpoint、工具、trace、权限、终止 | 阶段四–五：State + Runtime 层 |
| **Protocol / Eval** | 系统怎么互操作、怎么衡量 | 阶段六：Protocol + 附录 |

> 核心判断：**模型越强，不一定意味着系统越简单；它反而会迫使你重构系统。** 真正决定 Agent 能不能稳定上线的，是上下文怎么治理、工具怎么设计、长任务怎么维持状态、结果怎么验证、边界怎么控制。

---

## 🎯 你学完能收获什么

- **能从零跑通一个 Agent**：从第一次 LLM 调用，到工具循环、上下文治理、状态恢复、可观测、协议接入，全程不依赖 LangChain/LangGraph。
- **看懂任何框架**：亲手实现过 Harness，再用 LangChain / LangGraph / OpenAI Agents SDK 时，你会知道每一行背后在发生什么。
- **能讲清楚架构取舍**：循环怎么终止、上下文怎么压缩、工具失败怎么重试、何时用文件记忆何时用向量 —— 都能讲出工程理由，面试经得起追问。
- **对齐 2026 Agent 岗位**：配套[面试题库](面试题库.md)按 Agent Runtime、Context Engineering、MCP/A2A、Eval、Trace 等能力域组织，覆盖大厂高频追问。

---

## 🛠 技术栈

| 类别 | 选型 | 说明 |
| --- | --- | --- |
| **主语言** | Python 3.10+ | 全程 Python，不涉及 Java/Spring AI |
| **模型 SDK** | OpenAI 兼容 SDK | 默认 DeepSeek / 通义千问，可换 Ollama 本地模型（无需 Key） |
| **Agent 核心** | **自己手写** | Tool Loop、Context 治理、State、Checkpoint、Trace 全部从零实现 |
| **协议** | MCP / A2A / Skills | 第 16 章接入，理解协议层为何成基础设施 |
| **记忆体系** | 文件/会话记忆 vs 向量记忆 | 主线讲取舍；手写最简向量库作教具/附录，再讲何时该上 Qdrant/Redis |
| **可观测** | 自打 Trace + Langfuse | 第 14 章从零做观测 |
| **部署** | FastAPI + Docker | 第 18 章从 demo 到可交付 |
| **评测** | 自建回归集 + RAGAS | 附录讲 Agent Eval 框架 |

---

## 📚 教程大纲（节选）

完整导航见 **[教程目录大纲](教程目录大纲.md)**。下面是规划全貌，标注「✅ 已发布」的章节可直接点开看。

### 🟢 阶段一：Prompt 层 —— 让模型动起来
- 01 LLM 调用与环境准备 ✅ 已发布
- 02 消息状态与上下文窗口 ✅ 已发布
- 03 Prompt 与结构化输出（规划中）

### 🔵 阶段二：Tool 层 —— 给 Agent 装手脚
- 04 Function Calling 原理（规划中）
- 05 手写第一个工具循环 ✅ 已发布
- 06 工具集合与容错 ✅ 已发布
- 07 结构化输出与 Schema 设计 ✅ 已发布

### 🟣 阶段三：Context 层 —— 管好模型的「工作内存」
- 08 Context 治理：压缩、取舍、按需读取 ✅ 已发布
- 09 记忆体系：文件 / 会话记忆 vs 向量记忆 ✅ 已发布

### 🟠 阶段四：State 层 —— 让长任务可恢复
- 10 任务拆解与 Planning ✅ 已发布
- 11 失败策略与反思 ✅ 已发布
- 12 Checkpoint 与状态恢复 ✅ 已发布

### 🔴 阶段五：Runtime 层 —— 封装你的 Harness
- 13 封装 Mini Agent Runtime ✅ 已发布
- 14 可观测：Trace / 日志 / 回放
- 15 终止条件 · 权限 · 安全

### 🟤 阶段六：Protocol 与实战
- 16 MCP / A2A / Skills 接入
- 17 实战项目：深度研究助手 Agent
- 18 部署交付：FastAPI + Docker

> 📎 附录：[全书术语表](全书术语表.md) · [面试题库](面试题库.md) · [新手常见问题](新手入门与常见问题.md) · [工具资源索引](工具导航与参考资料索引.md) · [更新日志](教程更新日志.md)

---

<a id="快速开始"></a>

## 🚀 快速开始

1. **克隆仓库并进入项目目录**

   ```bash
   git clone https://github.com/kittimzhe/build-agent-harness-from-scratch.git
   cd build-agent-harness-from-scratch
   ```

2. **准备环境**（推荐 Python 3.10）

   ```bash
   python3.10 -m venv .venv
   source .venv/bin/activate          # macOS/Linux
   # .venv\Scripts\activate           # Windows
   pip install -r requirements.txt
   ```

3. **配置 API Key**

   - 把根目录 `.env-example` 复制为 `.env`
   - 填入你的 API Key（推荐 DeepSeek 或通义千问，国内便宜稳定）
   - 不想用云 API？可改用 [Ollama 本地模型](新手入门与常见问题.md#用-ollama-免-key-跑通)（无需 Key）

4. **跑通第一个案例**

   ```bash
   python examples/01_hello_llm.py
   ```

   > 代码用 `find_dotenv()` 自动向上查找 `.env`，所以在仓库任意子目录运行都能读到配置。遇到报错见[新手入门与常见问题](新手入门与常见问题.md)。
   >
   > 跑通后可继续：`python examples/02_chat_history.py`（消息状态）、`python examples/05_tool_loop.py`（工具循环）、`python examples/06_tool_retry.py`（工具容错）、`python examples/07_structured_output.py`（结构化输出）、`python examples/08_context_governance.py`（Context 治理）、`python examples/09_memory.py`（记忆体系，全部无需 API）、`python examples/10_planning.py`（任务拆解与 Planning）、`python examples/11_reflection.py`（失败策略与反思）、`python examples/12_checkpoint.py`（断点续跑，全部无需 API）、`python examples/13_runtime.py`（封装 Mini Agent Runtime）——对应已发布的第 02 / 05 / 06 / 07 / 08 / 09 / 10 / 11 / 12 / 13 章。

---

## 📖 关于本仓库

- **目标**：做一套**真正讲清原理、全程可跑**的 Agent Harness 实战教程。不只告诉你「学什么」，更告诉你「框架替你做了什么、自己怎么从零实现」。
- **技术定位**：聚焦 **Python + 手写 Agent Runtime** 路线，**不走 LangChain/LangGraph 速成、也不走 Java/Spring AI**。读完这套，再用任何框架都得心应手。
- **内容构成**：18 章系统正文（持续更新，见顶部进度）+ 每章可运行源码 + 面试题库 + 术语表 + 实战项目。
- **代码结构**：内核在 `harness/`（随章节生长），案例在 `examples/`，正文用中文文件名。内核只加能力、不改已公开接口。
- **更新承诺**：Agent 技术栈在快速演进，本仓库会跟随 context / harness / runtime / protocol 这条主线持续更新。若有帮助，欢迎 **Star** ⭐。

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/image?repos=kittimzhe/build-agent-harness-from-scratch&type=date)]()

---

**仓库英文名**：`build-agent-harness-from-scratch` · **仓库中文名**：《从零手写 Agent Harness：从 Prompt 到 Runtime》
