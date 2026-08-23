# 贡献指南

欢迎为《从零手写 Agent Harness》贡献内容！无论是修错字、补案例、加章节，都非常欢迎。

## 如何贡献

1. **Fork** 本仓库
2. 新建分支：`git checkout -b feat/your-topic`
3. 提交修改，commit message 遵循：`feat: 新增 xxx` / `fix: 修复 xxx` / `docs: 文档 xxx`
4. 提交 Pull Request，描述清楚改了什么、为什么

## 内容规范

- **可运行优先**：每章配套代码必须能 `python examples/xx.py` 跑通，不要贴伪代码。
- **原理与实现并重**：讲清「为什么这么设计」再给代码。
- **不依赖重框架**：正文主线不引入 LangChain/LangGraph，如需对比，单独成节。
- **配图**：放 `images/<章节号>/` 下，命名 `<章>-<节>-<序>.png`。
- **术语**：首次出现给中英对照，并尽量收录进[全书术语表](全书术语表.md)。

## 代码演进规则（重要）

本仓库的代码是「一个会生长的 Agent Runtime」，请遵守：

- **内核在 `harness/`，案例在 `examples/`**。正文 markdown 用中文文件名，代码用英文路径。
- **内核只加能力、不改已公开接口**。`LLMClient.chat` 的签名从第 01 章起冻住；加能力通过新方法或新字段，不破坏老调用方。
- **每章案例从仓库根目录 `python examples/xx.py` 跑通**，不要 `sys.path.insert`；配置用 `find_dotenv(usecwd=True)` 自动向上查找 `.env`。
- **对外返回自己的结构**（如 `LLMResult`），不把 OpenAI SDK 对象漏进上层循环。
- **不要为目录美观新增空的 `案例与源码-N` 文件夹**，也**不要先生成 02–18 的空 markdown 骨架**（空文件比死链更糟）。

## 提 Issue

- 发现错误、缺案例、有建议，都欢迎提 Issue。
