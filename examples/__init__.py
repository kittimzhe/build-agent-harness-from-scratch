"""examples —— 每章一份可运行案例。

命名规则：`<章号>_<主题>.py`，现有：
- `01_hello_llm.py`    第一次调用（同步 + 流式）
- `02_chat_history.py` 消息状态（记忆 / token 账单 / 截断）
- `05_tool_loop.py`    工具循环（单轮 / 链式 / 护栏）

运行方式：在仓库任意子目录 `python examples/01_hello_llm.py` 都能跑
（代码内部用 find_dotenv 自动向上查找 .env）。
"""
