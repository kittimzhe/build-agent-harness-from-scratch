# 18 - 部署交付：FastAPI + Docker

> 📌 **第 18 章 · 阶段六 Protocol 与实战（收官）** · [← 返回目录大纲](教程目录大纲.md) · [上一章 17 实战项目：深度研究助手 →](17-实战项目深度研究助手.md)

---

**本章课程目标：**

- 说清「demo → 可上线服务」的三层：**服务化**（FastAPI 暴露 HTTP）、**容器化**（Docker 打成镜像）、**可运行**（healthcheck + 密钥注入 + 无状态）。
- 掌握把 Agent 包成 HTTP 服务的三条原则：**无状态**（每请求独立 workdir）、**只露协议**、**密钥不进镜像**。
- 亲手把第 17 章的 `DeepResearchAgent` 包成 `POST /research`，能 `curl` 能 `docker run`。
- 全书收官：从第 01 章的「一个 LLM 调用」到第 18 章的「一个可上线服务」，主线闭环。

**学习建议：** 本章代码**离线冒烟不需要 API Key**（`DEEP_RESEARCH_OFFLINE=1`）。真实研究再配 `.env`。

---

## 1、从 demo 到上线，差的就是这三层

前面 17 章把 Agent 内核和实战项目都做出来了，但还差「最后一公里」：

| 层 | 解决什么 | 本章落点 |
| --- | --- | --- |
| **服务化** | 别人怎么调用你的 Agent | `FastAPI`：`GET /health` + `POST /research` |
| **容器化** | 换个机器怎么还能跑 | `Dockerfile`：依赖 + 代码 + 启动命令 |
| **可运行** | 跑起来之后怎么活下来 | `/health` 存活探针（编排器周期打点）/ 密钥不含在镜像里 |

> 一句话：**内核是大脑，HTTP 是皮肤，Docker 是盔甲。** 皮肤定接口、盔甲管交付，大脑（前 17 章）一个字节都不用改。

---

## 2、三条部署原则

1. **无状态**：每个请求独立建一个 `DeepResearchAgent` **+ 独立 workdir**（`base/req-<uuid>`）。为什么？Agent 带记忆（第 09 章）和检查点（第 12 章），若共享进程单例**或共享目录**，用户 A 的笔记/checkpoint 会串进用户 B 的报告——串味不只发生在进程里，也发生在文件层。**请求即用即弃；要续跑，显式带响应里返回的 `checkpoint_id` 复用该目录。**
2. **只露协议**：请求/响应用 Pydantic 模型定死（`ResearchRequest` / `ResearchResponse`），内核的私有结构（LLMResult / Plan / TraceEvent 之类）**不流出 HTTP**。这也是第 01 章「内核只认自己的结构、不向 SDK 泄漏」在服务层的翻版。
3. **密钥不进镜像**：`.env` 不进 `docker build`，运行时用 `--env-file .env` 或 `-e DEEPSEEK_API_KEY=...` 注入。

---

## 3、服务化：FastAPI 两个端点就够了

```python
GET  /health        # 存活探针 → {"status": "ok", "offline": ...}
POST /research      # body {question, plan?, max_steps} → {report, final_state, rounds, tool_calls, trace_file}
```

`_build_agent(workdir)` 是唯一的分叉点：`DEEP_RESEARCH_OFFLINE=1` 时用 `ScriptedLLM` + `FakeSearchEngine` 冒烟（无外部依赖），否则 `LLMClient()` 真实研究。`workdir` 由 `_workdir_for()` 决定：新请求拿 `base/req-<uuid>` 新目录，带 `checkpoint_id` 的请求复用旧目录并 `resume=True`。

> 为什么端点这么少？因为**复杂在 agent 内部（前 17 章），不在接口**。接口只负责「收问题、回报告」，剩下的交给 `DeepResearchAgent.research()`。

---

## 4、容器化：Dockerfile 三层

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements-full.txt ./        # ① 依赖层
RUN pip install --no-cache-dir -r requirements-full.txt
COPY harness ./harness                                 # ② 代码层
COPY projects ./projects
COPY deploy ./deploy
COPY .env-example ./.env-example
EXPOSE 8000
CMD ["uvicorn", "deploy.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

要点：**只 COPY 服务真正需要的目录**（harness / projects / deploy），`.env` 不 COPY（运行时注入）；依赖层放前面，代码改动时能吃到 Docker 层缓存。

---

## 5、内核复用清单（收官一页）

| 章 | 砖 | 在服务里的落点 |
| --- | --- | --- |
| 01 | `LLMClient` | 真实研究的脑 |
| 05/06 | Tool / 容错 | `_build_agent` 里的 `search_tool` |
| 08/09/10/11/12/14/15 | 治理/记忆/规划/反思/检查点/观测/安全 | 全在 `DeepResearchAgent.research()` 里，第 17 章已拼好 |
| 17 | `DeepResearchAgent` | 服务的一个「依赖」——皮肤下面包的就是它 |
| **18** | FastAPI + Docker | **皮肤 + 盔甲**：把上面全部包成可调用服务 |

> 看这张表最该记住的：**前 17 章一行没改**，第 18 章只是给它们穿了层衣服。这就是「内核与应用分离」的回报。

---

## 6、运行案例

**本地 + 离线冒烟（无 API）：**

```bash
pip install -r requirements-full.txt
DEEP_RESEARCH_OFFLINE=1 uvicorn deploy.app:app --port 8000
```

另开一个终端：

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","offline":true}

curl -X POST http://127.0.0.1:8000/research \
     -H 'Content-Type: application/json' \
     -d '{"question": "LangGraph 和 MCP 有什么关系？"}'
```

响应（确定性）：

```json
{
  "report": "## 报告（离线冒烟）\n服务链路打通…",
  "final_state": "done",
  "rounds": 2,
  "tool_calls": 0,
  "trace_file": ".deep_research/req-a1b2c3…/trace.jsonl",
  "checkpoint_id": "req-a1b2c3…"
}
```

> `rounds: 2` 是因为离线冒烟也走完整三阶段：① 规划阶段 `make_plan` 调一次 LLM 出步骤 JSON，② 综合阶段写报告再调一次。两个 LLM 调用都被 trace 记下——正好印证「只露协议」：内核里发生了两次 LLM 往返，对外只回一个 `rounds` 数字。

**Docker + 真实研究（需 API）：**

```bash
docker build -f deploy/Dockerfile -t deep-research-agent .
docker run --rm -p 8000:8000 --env-file .env deep-research-agent
```

> **盯两点**：① 接口只回了 `report/final_state/rounds/tool_calls/trace_file` 五个字段——内核的 Plan/TraceEvent/LLMResult 一个都没往外漏（只露协议）；② 离线模式 `offline: true` 是同一个接口、同一份代码，只是 `_build_agent` 分了个叉（离线替身 → 换真）。

---

## 7、常见报错排查

| 报错 / 现象 | 原因 | 解决 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'fastapi'` | 没装部署依赖 | `pip install -r requirements-full.txt` |
| 服务起了但真实研究报 API key 错 | `.env` 没配 / 没加载 | `--env-file .env`，或确认 `find_dotenv` 找得到 |
| `docker build` 卡在 pip | 网络 / 源慢 | 换 pip 源：`RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ...` |
| 容器里 `/research` 返回离线报告 | `DEEP_RESEARCH_OFFLINE=1` 带进去了 | 去掉该环境变量 / 用 `--env-file .env` |
| 两个用户报告串味 | 共享了进程单例**或共享 workdir** | 每请求独立 workdir（`req-<uuid>`）；续跑显式带 `checkpoint_id` |

更多见 [新手入门与常见问题](新手入门与常见问题.md)。

---

## 8、全书收官：这一路你建了什么

回看这个仓库，你从一行「调 LLM」的代码，一路加砖，到最后：

1. **能打电话**（01 调 LLM）→ **记得住对话**（02 状态）→ **会动手**（05 工具循环）
2. **扛得住**（06 容错）→ **输出可信**（07 结构化）→ **脑子不乱**（08 治理）→ **不忘事**（09 记忆）
3. **会规划**（10）→ **会反思**（11）→ **赔得起重试**（12）→ **封得住状态**（13）
4. **看得见**（14）→ **控得住**（15）→ **接得进世界**（16）→ **拼得出项目**（17）→ **上得了线**（18）

一共 **十四条内核主线 + 一个实战项目 + 一次部署交付**。这不是「又一套 Agent 手写范式课」，而是一条 **从 Prompt 到 Runtime 到服务** 的完整链路。

✅ **你现在已经能：**

- 用 FastAPI 把 Agent 包成 HTTP 服务，端点少而清晰
- 说清并落地「无状态 / 只露协议 / 密钥不进镜像」三条部署原则
- 用 Dockerfile 把服务打成可复现镜像，`docker run` 直接跑
- 说清「内核是大脑、HTTP 是皮肤、Docker 是盔甲」的分层

➡️ **收官之后**：入门已经走完。接下来可以往三个方向深挖——**效果**（微调 / 评测 / 痕迹学）、**深度**（多智能体协作 / 复杂规划范式）、**规模**（流式 / 分布式 tracing / 权限体系生产化）。这些的「地基」——你把前 18 章走完一遍就有了。可返回[教程目录大纲](教程目录大纲.md)回顾全局。