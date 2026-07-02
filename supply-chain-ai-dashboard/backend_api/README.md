# 后端 API 服务 (Backend API Service)

本模块是整个供应链智能分析看板的 **主控后端**。基于 FastAPI 构建，负责接收实时回放的订单流、调用 AI 推理微服务打分、进行 MySQL 订单和告警持久化、维护 Redis KPI 缓存，并通过 WebSocket 长连接将最新数据及风险告警毫秒级广播分发给前端大屏。

## 📂 目录结构

```text
backend_api/
├── app/
│   ├── api/          # 路由控制层 (REST 接口与 WebSocket 路由)
│   ├── core/         # 系统全局配置 (config.py) 与安全过滤 (security.py)
│   ├── db/           # SQLAlchemy 数据库映射与 KPI 计算逻辑
│   ├── services/     # 缓存代理 (cache.py) 与 AI 推理接口适配 (model_runner.py)
│   ├── ws/           # WebSocket 多端连接管理器 (manager.py)
│   ├── main.py       # FastAPI 启动文件
│   └── schemas.py    # Pydantic 强契约数据结构体
├── Dockerfile        # 容器化构建配置文件
├── requirements.txt  # Python 依赖项 (FastAPI, SQLAlchemy, Redis, Httpx, WebSockets)
└── dev.db            # SQLite 本地临时开发数据库 (不使用 Docker 时自动创建)
```

---

## ⚙️ 核心配置环境变量

在运行后端时，主要配置参数来自环境变量：

| 环境变量 | 默认值 | 作用说明 |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///dev.db` | 关系型数据库连接串 (不设置时默认使用本地 SQLite 数据库文件) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis KPI 缓存与 WSS 频道发布订阅连接串 |
| `AI_SERVICE_URL` | `""` | AI 推理微服务的基本地址 (例如 `http://127.0.0.1:8081`) |
| `INGEST_API_KEY` | `""` | 校验回放端数据注入的 API Key (为空则不校验) |
| `INGEST_HMAC_SECRET` | `""` | 校验回放端 HMAC 签名的密钥 (为空则不校验签名) |
| `AI_SERVICE_API_KEY` | `""` | 调用 AI 微服务时发送的 API Key 凭证 |
| `AI_SERVICE_HMAC_SECRET`| `""` | 调用 AI 微服务时用于加密签名的密钥 |

---

## 🚀 启动与调试

### 1. 本地直接开发 (SQLite 模式)
在 SQLite 模式下，后端会自动关闭 Redis 缓存与 WSS 发布频道（退退到 WebSocket 内存广播模式），并自动在 `backend_api` 根目录下建立 `dev.db`：
```bash
cd supply-chain-ai-dashboard
# 激活虚拟环境并安装依赖
.\.venv\Scripts\activate
pip install -r backend_api/requirements.txt

# 启动服务
uvicorn backend_api.app.main:app --reload --port 8000
```
启动后访问接口文档页：`http://localhost:8000/docs`。

### 2. VPS 与生产环境启动 (Docker Compose)
在主目录下进行一键启动，后端会自动连接到同网络中的 MySQL 8.0 与 Redis 7.0：
```bash
docker compose up -d --build backend-api
```

---

## 🛡️ 安全验证与容灾处理

1. **HMAC 校验**：在 `/stream/ingest` 入口对请求执行严格的时间戳防重放校验（默认最大允许时差为 300 秒），并根据 HMAC-SHA256 算法逆向计算签名体。
2. **AI 推理服务容灾**：当远端 `ai-service` 挂起或通信超时时，后端会自动截获 httpx 异常并降级为 `history-fallback` 销量趋势，数据基于 MySQL 数据库中的历史算术均值进行拟合，确保可视化大屏在算法脑离线时依然保持高可用决策，不断线。
