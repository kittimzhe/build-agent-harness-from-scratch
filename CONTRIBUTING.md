# 贡献指南

欢迎为《从零手写 Agent Harness》贡献内容！无论是修错字、补案例、加章节，都非常欢迎。

## 如何贡献

1. **Fork** 本仓库
2. 新建分支：`git checkout -b feat/your-topic`
3. 提交修改，commit message 遵循：`feat: 新增 xxx` / `fix: 修复 xxx` / `docs: 文档 xxx`
4. 提交 Pull Request，描述清楚改了什么、为什么

## 本地运行与测试

测试与 05–17 章离线案例**都不需要 API Key**（用确定性替身 / `ScriptedLLM`），新环境三步即可：

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest        # 只跑单测；跑部署冒烟再加装 requirements-full.txt
python -m pytest tests/              # 20 条，无需 API Key
```

- **离线案例**：`python examples/05_tool_loop.py`（05 章起案例默认离线替身；`--real` 才要 Key）
- **部署冒烟**（无 API）：`DEEP_RESEARCH_OFFLINE=1 python deploy/smoke_test.py`（需 `pip install -r requirements-full.txt`，httpx 由 openai 依赖带入）
- **真实研究**才需要 `.env`：复制 `.env-example` 填 Key，`python examples/05_tool_loop.py --real` 或跑第 17/18 章真模型路径

> CI（`.github/workflows/ci.yml`）会把「语法检查 → pytest → demos 05–16 → 17 离线 → 18 FastAPI 冒烟」整条跑一遍，全离线、无 Key，提交前可先在本地复现。

## 内容规范

- **可运行优先**：每章配套代码必须能 `python examples/xx.py` 跑通，不要贴伪代码。
- **原理与实现并重**：讲清「为什么这么设计」再给代码。
- **不依赖重框架**：正文主线不引入 LangChain/LangGraph，如需对比，单独成节。
- **配图**：放 `images/<章节号>/` 下，命名 `<章>-<节>-<序>.png`。
- **术语**：首次出现给中英对照，并尽量收录进[全书术语表](全书术语表.md)。

## 代码演进规则（重要）

本仓库的代码是「一个会生长的 Agent Runtime」，请遵守：

- **内核在 `harness/`，案例在 `examples/`**。正文 markdown 用中文文件名，代码用英文路径。
- **内核只加能力、不改已公开接口**。`LLMClient.chat` / `ChatSession.ask` / `AgentLoop.run` 的签名从各自章节起冻住；加能力通过新方法或新字段，不破坏老调用方。
- **每章案例 `python examples/xx.py` 必须能跑通**（在仓库任意子目录都行，配置用 `find_dotenv(usecwd=True)` 自动向上查找 `.env`）。案例里允许用「相对于仓库根的 `sys.path.insert`」来 import `harness`（第 01 章这样比一上来教 `pip install -e .` 更轻）；**内核本身不要靠 `sys.path`**。
- **案例的环境自检读内核的 `PROVIDERS`**，不要在案例里重复维护提供商表（换提供商会改两处）。
- **对外返回自己的结构**（如 `LLMResult`、纯 dict），不把 OpenAI SDK 对象漏进上层循环。
- **不要为目录美观新增空的 `案例与源码-N` 文件夹**，也**不要先生成未发布章节的空 markdown 骨架**（空文件比死链更糟）。

## 发章 checklist（每发一章必过）

发新章时逐项打勾，一项都别漏（历史教训：页眉「下一章（规划中）」从 05 一路漏到 17）：

- [ ] `_sidebar.md`：本章转可点链接；阶段标题去掉「（规划中）」（如该阶段就此收尾）
- [ ] `README.md`：徽章章号、进度行、大纲节选「✅ 已发布」、快速开始命令
- [ ] `教程目录大纲.md`：本章小节加「✅ 已发布 + 链接」；顶部进度行
- [ ] **上一章页眉**：「下一章 XX（规划中）」→ 真链接（文件第 3 行那个 `> 📌` 行）
- [ ] 上一章文末：「➡️ 下一章」转真链接
- [ ] `新手入门与常见问题.md` §4：补本章运行命令
- [ ] `examples/__init__.py`：补本章案例条目（如适用）
- [ ] `全书术语表.md`：本章新术语
- [ ] `面试题库.md`：本章 5 题带答法要点
- [ ] `教程更新日志.md`：新条目
- [ ] 验证：语法检查 + 离线单测 + demo 实跑输出与正文一致 + 引用文件存在

## 提 Issue

- 发现错误、缺案例、有建议，都欢迎提 Issue。
