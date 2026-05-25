# Docker 统一部署说明

## 1. 统一入口

项目 Docker 部署统一从仓库根目录执行，不再进入各子模块单独运行 compose。

```bash
cp .env.example .env
docker compose up -d --build
```

启动完成后访问：

- 前端大屏：`http://localhost`
- 后端 Swagger：`http://localhost:8000/docs`
- 后端健康检查：`http://localhost:8000/health`
- AI 推理服务 Swagger：`http://localhost:8081/docs`

## 2. 服务编排

根目录 `docker-compose.yml` 统一编排以下服务：

- `mysql-db`：MySQL 8.0，持久化订单与告警数据。
- `redis-cache`：Redis 7.0，缓存 KPI 与发布告警消息。
- `ai-service`：算法推理微服务，提供 `/predict/risk`。
- `backend-api`：FastAPI 主服务，提供 REST API 与 WebSocket。
- `frontend-dashboard`：Vue 构建产物 + Nginx，代理 `/api` 到后端。
- `data-replay`：数据回放容器，使用 `replay` profile 手动启用。

## 3. 常用命令

```bash
# 启动完整演示环境
docker compose up -d --build

# 查看服务状态
docker compose ps

# 查看后端日志
docker compose logs -f backend-api

# 只重建后端
docker compose up -d --build backend-api

# 启动数据回放任务
docker compose --profile replay up data-replay --build

# 停止并保留数据库数据
docker compose down

# 停止并清理数据库 volume
docker compose down -v
```

## 4. 联调约定

- 浏览器只访问 `frontend-dashboard` 暴露的 `http://localhost`。
- 前端请求 `/api/...`，由 Nginx 代理到 `backend-api:8000`。
- 前端 WebSocket 连接 `/api/v1/ws/alerts`，由 Nginx 透传 Upgrade。
- 后端通过 `AI_SERVICE_URL=http://ai-service:8000` 调用 AI 服务。
- 数据回放容器通过 `BACKEND_INGEST_URL=http://backend-api:8000/api/v1/stream/ingest` 注入订单。

## 5. 后端本地开发

不使用 Docker 时，后端默认使用 `backend_api/dev.db` 作为 SQLite 开发库，便于本地快速调试。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend_api/requirements.txt
uvicorn backend_api.app.main:app --reload --port 8000
```

## 6. 前端本地开发

Vite 已配置 `/api` 代理到本地后端 `http://localhost:8000`，WebSocket 也走同一个 `/api/v1/ws/alerts` 路径。

```bash
cd frontend_ui/frontend_ui_v1
npm install
npm run dev
```
