"""16_protocol.py —— 第 16 章案例：MCP / A2A / Skills 接入

运行方式（仓库任意子目录）：
    python examples/16_protocol.py

本章全部 demo **不需要 API Key**：协议交互用 FakeLLM 确定性演示。

演示结构：
    1. MCP：server 定义工具 / client 列出并调用（tools/list + tools/call）
    2. MCP 接入 MiniAgent：远程 MCP 工具被适配成本框架 Tool，模型无感知调用
    3. A2A：把另一个 Agent 包装成工具，本 Agent 调「专家」协作
    4. Skills：技能库 catalog + 按需 activate（挂载 prompt + 工具）
    5. 三者对比：同一个世界，三种接入缝
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import (
    MCPTool, MCPServer, MCPClient, AgentEndpoint, a2a_tool,
    Skill, SkillLibrary, Tool, MiniAgent, LLMResult,
)


def get_weather(city: str) -> str:
    """查某城市天气"""
    return f"{city}：晴 25℃"


class StaticLLM:
    """确定性 LLM：永远直接给终答。"""
    def __init__(self, text):
        self.text = text
    def chat(self, messages, **kwargs):
        return LLMResult(content=self.text, tool_calls=[])


class CallToolThenAnswer:
    """确定性 LLM：第一轮回一次工具，第二轮给终答。"""
    def __init__(self, tool_name, arguments, final):
        self.tool_name, self.arguments, self.final = tool_name, arguments, final
        self.calls = 0
    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return LLMResult(content=None, tool_calls=[{
                "id": "c1", "type": "function",
                "function": {"name": self.tool_name, "arguments": self.arguments},
            }])
        return LLMResult(content=self.final, tool_calls=[])


# ---------- demo ----------

def demo_mcp_raw():
    """① MCP：tools/list + tools/call。"""
    print("=" * 60)
    print("① MCP：谁定义工具（server）、谁用工具（client）解耦")
    print("=" * 60)
    server = MCPServer(tools=[MCPTool("get_weather", "查天气",
                                      {"type": "object",
                                       "properties": {"city": {"type": "string"}}},
                                      get_weather)])
    client = MCPClient(server)
    print("  tools/list →", client.list_tools())
    print("  tools/call →", client.send({"method": "tools/call",
                                         "params": {"name": "get_weather",
                                                    "arguments": {"city": "北京"}}}))
    print("  （真 MCP 是 JSON-RPC over stdio/SSE/HTTP；这里只传协议形状）\n")


def demo_mcp_into_agent():
    """② MCP 接入 MiniAgent。"""
    print("=" * 60)
    print("② MCP 接入 MiniAgent：远程工具被适配成本框架 Tool，模型无感知")
    print("=" * 60)
    server = MCPServer(tools=[MCPTool("get_weather", "查天气",
                                      {"type": "object",
                                       "properties": {"city": {"type": "string"}}},
                                      get_weather)])
    client = MCPClient(server)
    harness_tools = client.to_harness_tools()
    print(f"  适配后的工具：{[t.name for t in harness_tools]}（就是普通 Tool）")

    llm = CallToolThenAnswer("get_weather", '{"city": "上海"}', "上海是晴天，25℃")
    agent = MiniAgent(llm=llm, system="你是天气助手", tools=harness_tools, name="wx")
    out = agent.run("上海天气？")
    print(f"  reply={out['reply']}")
    print("  （MiniAgent 完全不知道 get_weather 在「远程」——MCP 把位置透明化了）\n")


def demo_a2a():
    """③ A2A：调另一个 Agent 当专家。"""
    print("=" * 60)
    print("③ A2A：把「另一个 Agent」包装成工具，当专家来调")
    print("=" * 60)
    expert = MiniAgent(llm=StaticLLM("专家结论：等于 42"), system="你是数学专家", name="expert")
    endpoint = AgentEndpoint(expert, "expert")
    ask_expert = a2a_tool(endpoint)
    print(f"  专家被包装成工具：{ask_expert.name}")

    boss_llm = CallToolThenAnswer("ask_expert", '{"message": "1+2 等于几？"}',
                                  "按照专家的说法，答案是 42")
    boss = MiniAgent(llm=boss_llm, system="你是总协调", tools=[ask_expert], name="boss")
    out = boss.run("问专家 1+2")
    print(f"  boss 最终回复：{out['reply']}")
    print("  （拉平「差一个工具」和「差一个专家」：对调用方都是跑一下拿结果）\n")


def demo_skills():
    """④ Skills：技能库 catalog + activate。"""
    print("=" * 60)
    print("④ Skills：把「提示词 + 工具 + 用法」打包成资产，按需挂载")
    print("=" * 60)
    lib = SkillLibrary()
    lib.add(Skill(name="report", description="生成周报",
                  prompt="你是周报专家：先拉数据再算总额再画图。",
                  tools=[Tool(get_weather, name="get_weather", description="查天气")]))
    lib.add(Skill(name="translate", description="多语言翻译",
                  prompt="你是翻译专家：翻译下列文本。", tools=[]))
    print("  catalog 给模型看：")
    print("    " + lib.catalog().replace("\n", "\n    "))
    prompt, tools = lib.activate("report")
    print(f"  挂载 report：prompt[{prompt[:18]}…] + tools={[t.name for t in tools]}")
    print("  （按需挂载，别把所有技能一次性塞进 system prompt）\n")


def demo_compare():
    """⑤ 三者对比。"""
    print("=" * 60)
    print("⑤ 同一个世界，三种接入缝")
    print("=" * 60)
    print("  MCP    ：接『工具生态』——谁提供服务、谁消费服务解耦")
    print("  A2A    ：接『别的 Agent』——专家/同事也是可调用的能力")
    print("  Skills ：接『知识资产』——提示词+工具+用法打包，按需挂载")
    print("  共同点：都把自己『适配成本框架 Tool』，MiniAgent 调用面统一。\n")


def main():
    print()
    demo_mcp_raw()
    demo_mcp_into_agent()
    demo_a2a()
    demo_skills()
    demo_compare()
    print("✅ 本章全部 demo 无需 API Key，确定性输出完成。")


if __name__ == "__main__":
    main()