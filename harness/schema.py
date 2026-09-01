"""schema —— 结构化输出与 Schema 设计（Harness 第五块砖，第 07 章落地）。

第 05 章用 JSON Schema 约束了【工具入参】；第 07 章把同一思想用到【模型输出】：
让模型的回答不是一段自由文本，而是一个「程序能解析、规则能校验」的数据结构。
下游不再靠正则和祈祷，而是靠类型系统。

三个能力：
1. extract_json：从模型输出（可能带代码围栏 / 前后废话）里稳健地抠出 JSON
2. strict_validate：JSON → Pydantic 模型，做类型 / 必填 / 约束校验
3. structured_chat：调用 LLM + 解析 + 校验 + 解析失败时把错误回喂模型【自纠】

设计原则延续：`LLMClient.chat` / `AgentLoop.run` 签名不动，结构化输出是 chat 之上的一层包装。
"""

from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """结构化输出的解析 / 校验失败。message 会被当作提示回喂给模型自纠。"""


def extract_json(text: str) -> str:
    """从模型输出里稳健地提取 JSON 字符串。

    模型输出常带 ```json ... ``` 围栏、或「好的，结果如下」这类前后缀，
    还有可能把 JSON 嵌在解释里。这里先剥围栏，再取最外层的 { ... }，容错常见格式漂移。
    """
    if not text:
        raise StructuredOutputError("模型返回了空内容")

    # 1) 剥掉 ```json ... ``` 围栏
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    # 2) 找最外层 { ... }（从最左 { 到最右 }，容忍前后有解释文字）
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise StructuredOutputError(f"模型输出里找不到 JSON：{text[:120]!r}")

    return text[start:end + 1]


def strict_validate(model_cls: Type[T], text: str) -> T:
    """把文本解析成 JSON，再用 Pydantic 模型严格校验。失败抛 StructuredOutputError。"""
    candidate = extract_json(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise StructuredOutputError(f"JSON 解析失败：{e}") from e
    try:
        return model_cls.model_validate(data)
    except ValidationError as e:
        raise StructuredOutputError(f"字段校验失败：{e}") from e


def structured_chat(llm, messages: list[dict], model_cls: Type[T],
                    max_retries: int = 2, json_mode: bool = True) -> T:
    """让 LLM 返回一个通过校验的 Pydantic 模型；解析失败时把错误回喂、让模型自纠。

    - json_mode=True: 请求带 `response_format={"type": "json_object"}`（JSON Mode，
      只保证「是合法 JSON」，形状靠下面的 schema 提示来约束）。
    - 每次失败：把「上一次的错误」作为一条 user 消息追加，让模型自己改——**自纠重试**。
    - 重试耗尽仍失败：抛 StructuredOutputError（信息里含最后一轮的校验错误）。

    注：OpenAI / DeepSeek 等还支持原生 structured output
    （`response_format={"type": "json_schema", ...}`，直接锁死结构），
    本层用「JSON Mode + schema 提示」是为了跨提供商通用；真要硬约束可自行换成原生。
    """
    schema = model_cls.model_json_schema()
    schema_prompt = (
        "你必须严格输出一个 JSON 对象，只输出 JSON、不要任何解释或代码围栏，"
        "并符合如下 JSON Schema：\n" + json.dumps(schema, ensure_ascii=False)
    )

    base = list(messages)
    if base and base[0].get("role") == "system":
        base[0] = {"role": "system", "content": base[0]["content"] + "\n\n" + schema_prompt}
    else:
        base.insert(0, {"role": "system", "content": schema_prompt})

    history = base
    last_err = ""
    for attempt in range(max_retries + 1):
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        result = llm.chat(history, **kwargs)
        answer = result.content or ""
        try:
            return strict_validate(model_cls, answer)
        except StructuredOutputError as e:
            last_err = str(e)
            history.append({
                "role": "user",
                "content": (
                    f"你上一次的输出没有通过校验，错误如下：\n{e}\n"
                    f"请修正后重新输出，只输出符合要求的 JSON，不要解释。"
                ),
            })
    raise StructuredOutputError(f"经过 {max_retries + 1} 次尝试仍未通过校验。最后错误：{last_err}")