# Deep Research Agent 服务 —— Docker 镜像
#
# 构建：
#   docker build -f deploy/Dockerfile -t deep-research-agent .
# 运行（离线冒烟，无 API）：
#   docker run --rm -p 8000:8000 -e DEEP_RESEARCH_OFFLINE=1 deep-research-agent
# 运行（真实研究，注入密钥）：
#   docker run --rm -p 8000:8000 --env-file .env deep-research-agent

FROM python:3.11-slim

WORKDIR /app

# 依赖层（含 fastapi/uvicorn，见 requirements-full.txt）
COPY requirements.txt requirements-full.txt ./
RUN pip install --no-cache-dir -r requirements-full.txt

# 代码层（只 COPY 服务真正需要的目录，.env 不进镜像、运行时注入）
COPY harness ./harness
COPY projects ./projects
COPY deploy ./deploy
COPY .env-example ./.env-example

EXPOSE 8000

# 单进程即可；要并发扩缩，用 Gunicorn/Uvicorn workers + 前面挂负载均衡
CMD ["uvicorn", "deploy.app:app", "--host", "0.0.0.0", "--port", "8000"]