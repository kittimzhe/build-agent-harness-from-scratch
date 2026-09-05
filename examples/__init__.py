"""examples —— 每章一份可运行案例。

命名规则：`<章号>_<主题>.py`，现有：
- `01_hello_llm.py`          第一次调用（同步 + 流式）
- `02_chat_history.py`       消息状态（记忆 / token 账单 / 截断）
- `05_tool_loop.py`          工具循环（单轮 / 链式 / 护栏）
- `06_tool_retry.py`         工具容错（重试 / 超时 / 幂等）
- `07_structured_output.py`  结构化输出（Schema / 自纠）
- `08_context_governance.py` Context 治理（压缩 / 取舍 / 按需读取）
- `09_memory.py`             记忆体系（文件 / 向量，全部无需 API）
- `10_planning.py`           任务拆解与 Planning
- `11_reflection.py`         失败策略与反思
- `12_checkpoint.py`         断点续跑 / 状态恢复（全部无需 API）
- `13_runtime.py`            封装 Mini Agent Runtime
- `14_trace.py`              可观测 Trace/日志/回放
- `15_safety.py`             终止条件·权限·安全（全部无需 API）
- `16_protocol.py`           MCP/A2A/Skills 接入（全部无需 API）

第 17/18 章不是 examples：实战项目在 `projects/deep_research/`，
部署服务在 `deploy/`。

运行方式：在仓库任意子目录 `python examples/01_hello_llm.py` 都能跑
（代码内部用 find_dotenv 自动向上查找 .env）。
"""