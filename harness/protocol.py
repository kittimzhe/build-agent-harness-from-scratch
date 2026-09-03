"""protocol —— MCP / A2A / Skills 接入（Harness 第十四块砖，第 16 章落地）。

内核前面 13 块砖把「单机 Agent」做齐了，第 16 章把 Agent 接进真实世界：

- MCP（Model Context Protocol）：谁定义工具（Server）、谁用工具（Client）解耦，
  MCPClient 把远程 MCP 工具适配成本框架的 Tool——MiniAgent 无感知地调用外部工具。
- A2A（Agent-to-Agent）：把「另一个 Agent」包装成一条工具，本 Agent 可调它协作。
  拉平「差一个工具」和「差一个专家」的区别。
- Skills：把「提示词 + 工具 + 用法说明」打包成可复用资产（skill），按需挂载，
  而不是把所有工具一次性塞进 system prompt。

教学级实现：传达协议「形状」，不做完整 spec 兼容（真 MCP 是 JSON-RPC over
stdio/SSE/HTTP，真 A2A 有完整 envelope）。关键是让你看懂三者的分工与接入缝。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from harness.loop import Tool


# ---------------------------------------------------------------------------
# MCP：工具「谁定义」与「谁使用」解耦
# ---------------------------------------------------------------------------

@dataclass
class MCPTool:
    """一个 MCP 工具的服务器端定义：名字 + 描述 + 参数 schema + 处理器。"""
    name: str
    description: str
    parameters: dict
    handler: Callable[..., str] = field(repr=False)

    def call(self, arguments: dict) -> str:
        return self.handler(**arguments)


class MCPServer:
    """极简 MCP Server：暴露 tools/list 和 tools/call 两个方法。

    真 MCP 走 JSON-RPC（jsonrpc/method/params/id envelope），这里直接方法名分派，
    让你看清协议核心就这两件事：列出有什么工具、调用某个工具。
    """

    def __init__(self, tools: list[MCPTool]):
        self.tools = {t.name: t for t in tools}

    def handle(self, request: dict) -> dict:
        method = request.get("method")
        if method == "tools/list":
            return {"tools": [
                {"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in self.tools.values()
            ]}
        if method == "tools/call":
            params = request.get("params", {})
            name, arguments = params.get("name"), params.get("arguments", {})
            tool = self.tools.get(name)
            if tool is None:
                return {"error": f"unknown tool: {name}"}
            try:
                return {"content": [{"type": "text", "text": tool.call(arguments)}]}
            except Exception as e:  # noqa: BLE001
                return {"error": str(e)}
        return {"error": f"unknown method: {method}"}


class MCPClient:
    """MCP Client：通过 transport 调远程 MCP Server，并把远程工具适配成本框架 Tool。

    transport 是一个 `request(dict) -> dict` 的通道——可以是内存里的 MCPServer，
    也可以是真实走 HTTP/stdio 的客户端。默认直接接一个 MCPServer。
    """

    def __init__(self, transport: Callable[[dict], dict] | MCPServer):
        self.send = transport.handle if isinstance(transport, MCPServer) else transport

    def list_tools(self) -> list[dict]:
        return self.send({"method": "tools/list"}).get("tools", [])

    def to_harness_tools(self) -> list[Tool]:
        """把 MCP 工具全部适配成本框架的 Tool（MiniAgent 零改动即可调用）。"""
        return [self._adapt(m) for m in self.list_tools()]

    def _adapt(self, meta: dict) -> Tool:
        name = meta["name"]
        description = meta.get("description", "")
        parameters = meta.get("parameters", {})

        def _invoke(**kwargs):
            resp = self.send({"method": "tools/call",
                              "params": {"name": name, "arguments": kwargs}})
            if "error" in resp:
                raise RuntimeError(resp["error"])
            return resp["content"][0]["text"]

        # 注意：Tool 的 parameters 直接用远程侧给的 schema；handler 走远程调用。
        return Tool(_invoke, name=name, description=description, parameters=parameters)


# ---------------------------------------------------------------------------
# A2A：把「另一个 Agent」包装成一条工具
# ---------------------------------------------------------------------------

class AgentEndpoint:
    """一个 Agent 的对外接口：别的 Agent 通过 send() 发消息、拿结果。"""
    def __init__(self, agent, name: str):
        self.agent = agent
        self.name = name

    def send(self, message: str) -> str:
        out = self.agent.run(message)
        return out.get("reply", "")


def a2a_tool(endpoint: AgentEndpoint, name: str | None = None) -> Tool:
    """把「另一个 Agent」包装成一条工具：本 Agent 调它 = 向专家发一条消息。

    拉平了「差一个工具」和「差一个专家」的区别——对调用方都是 `跑一下、拿结果`。
    """
    tool_name = name or f"ask_{endpoint.name}"

    def _ask(message: str) -> str:
        return endpoint.send(message)

    return Tool(_ask, name=tool_name,
                description=f"把这个消息转给专家「{endpoint.name}」并拿回它的回答",
                parameters={"type": "object", "properties": {"message": {"type": "string"}}})


# ---------------------------------------------------------------------------
# Skills：把「提示词 + 工具 + 用法」打包成可复用资产
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """一个技能资产：何时用（description）+ 怎么用（prompt）+ 配了什么工具。"""
    name: str
    description: str
    prompt: str = ""
    tools: list[Tool] = field(default_factory=list)


class SkillLibrary:
    """技能库：按需挂载，别把所有技能一次性塞进 system prompt。"""

    def __init__(self, skills: list[Skill] | None = None):
        self.skills: dict[str, Skill] = {s.name: s for s in (skills or [])}

    def add(self, skill: Skill) -> "SkillLibrary":
        self.skills[skill.name] = skill
        return self

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def catalog(self) -> str:
        """给模型看的技能清单（一句何时用）。"""
        if not self.skills:
            return "(无可用技能)"
        return "\n".join(f"- {s.name}: {s.description}" for s in self.skills.values())

    def activate(self, name: str) -> tuple[str, list[Tool]]:
        """挂载某技能：返回（prompt 片段, 工具列表），上层拼进 system/工具集。"""
        s = self.get(name)
        if s is None:
            raise KeyError(f"unknown skill: {name}")
        return s.prompt, list(s.tools)