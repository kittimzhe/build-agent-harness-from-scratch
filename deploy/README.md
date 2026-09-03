# 部署交付（第 18 章）

把第 17 章的深度研究助手包成可上线 HTTP 服务，再打进 Docker。

## 目录

```
deploy/
├── app.py        # FastAPI：GET /health + POST /research
└── Dockerfile    # 可复现镜像
```

## 本地跑

```bash
pip install -r requirements-full.txt

# 真实研究（需 .env 配好 API，见第 01 章）
uvicorn deploy.app:app --reload

# 离线冒烟（无 API）
DEEP_RESEARCH_OFFLINE=1 uvicorn deploy.app:app --port 8000
```

## 调接口

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/research \
     -H 'Content-Type: application/json' \
     -d '{"question": "LangGraph 和 MCP 有什么关系？"}'
```

响应：

```json
{
  "report": "# 研究报告…",
  "final_state": "done",
  "rounds": 1,
  "tool_calls": 0,
  "trace_file": ".deep_research/trace.jsonl"
}
```

## Docker

```bash
docker build -f deploy/Dockerfile -t deep-research-agent .
docker run --rm -p 8000:8000 -e DEEP_RESEARCH_OFFLINE=1 deep-research-agent
# 真实研究：docker run --rm -p 8000:8000 --env-file .env deep-research-agent
```

## 设计原则

- **无状态**：每请求独立 agent，避免跨用户记忆/检查点串味。
- **只露协议**：请求/响应走 Pydantic 模型，内核私有结构不流出 HTTP。
- **密钥不进镜像**：`.env` 运行时 `--env-file` / `-e` 注入。