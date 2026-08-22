# 贡献指南

欢迎为《从零手写 Agent Harness》贡献内容！无论是修错字、补案例、加章节，都非常欢迎。

## 如何贡献

1. **Fork** 本仓库
2. 新建分支：`git checkout -b feat/your-topic`
3. 提交修改，commit message 遵循：`feat: 新增 xxx` / `fix: 修复 xxx` / `docs: 文档 xxx`
4. 提交 Pull Request，描述清楚改了什么、为什么

## 内容规范

- **可运行优先**：每章配套代码必须能 `python xxx.py` 跑通，不要贴伪代码。
- **原理与实现并重**：讲清「为什么这么设计」再给代码。
- **不依赖重框架**：正文主线不引入 LangChain/LangGraph，如需对比，单独成节。
- **配图**：放 `images/<章节号>/` 下，命名 `<章>-<节>-<序>.png`。
- **术语**：首次出现给中英对照，并尽量收录进[全书术语表](全书术语表.md)。

## 提 Issue

- 发现错误、缺案例、有建议，都欢迎提 Issue。
