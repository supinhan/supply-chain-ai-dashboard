# AI 赋能企业供应链可视化分析系统

本项目是一个面向 MVP 演示的供应链可视化与智能预警系统。系统使用 Kaggle DataCo 供应链数据集模拟实时订单流，通过后端服务调用 AI 风险模型完成在线评分，并将实时 KPI 与高风险告警推送到前端大屏。

当前阶段目标是跑通基础闭环：

```text
DataCo CSV 回放 -> FastAPI 后端接收 -> AI 风险评分 -> MySQL/Redis 写入 -> WebSocket 推送 -> Vue 大屏展示
```

## 功能概览

- 数据回放：从 `DataCoSupplyChainDataset.csv` 读取订单数据，按指定速率注入后端。
- 订单接入：后端提供 `POST /api/v1/stream/ingest` 接收实时订单。
- AI 风险评分：后端调用独立 AI 微服务 `/predict/risk`，返回风险概率与解释信息。
- 风险告警：高风险订单生成告警记录，并通过 WebSocket 实时推送。
- KPI 看板：提供累计订单量、GMV、准交率、风险次数、延迟率和热力数据。
- 统一部署：使用 Docker Compose 编排 MySQL、Redis、AI 服务、后端、前端和数据回放服务。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端大屏 | Vue 3, Vite, ECharts, Nginx |
| 后端 API | Python 3.10+, FastAPI, SQLAlchemy |
| AI 服务 | Python, Scikit-learn, Pandas, Joblib |
| 数据存储 | MySQL 8.0, Redis 7.0 |
| 数据回放 | Python, CSV, Requests |
| 部署 | Docker, Docker Compose |

## 项目结构

```text
.
├── README.md
└── supply-chain-ai-dashboard/
    ├── ai_algorithms/
    │   └── supplychain-ai-service/      # AI 推理服务与模型文件
    ├── backend_api/                     # FastAPI 后端主服务
    │   ├── app/
    │   │   ├── api/                     # REST 与 WebSocket 路由
    │   │   ├── core/                    # 配置
    │   │   ├── db/                      # SQLAlchemy 模型与查询
    │   │   ├── services/                # AI 调用、Redis 适配
    │   │   └── ws/                      # WebSocket 连接管理
    │   └── requirements.txt
    ├── data_producer/                   # DataCo 数据回放脚本与数据集
    ├── docs/                            # PRD、SDD、部署说明、任务分工等文档
    ├── frontend_ui/
    │   └── frontend_ui_v1/              # Vue 3 可视化大屏
    └── docker-compose.yml               # 统一服务编排入口
```

## 快速启动

进入应用主目录：

```bash
cd supply-chain-ai-dashboard
```

复制环境变量示例文件：

```bash
cp .env.example .env
```

启动完整演示环境：

```bash
docker compose up -d --build
```

启动完成后访问：

- 前端大屏：`http://localhost`
- 后端 Swagger：`http://localhost:8000/docs`
- 后端健康检查：`http://localhost:8000/health`
- AI 服务 Swagger：`http://localhost:8081/docs`

查看服务状态：

```bash
docker compose ps
```

停止服务：

```bash
docker compose down
```

清理数据库 volume 后重新演示：

```bash
docker compose down -v
docker compose up -d --build
```

## 数据回放

数据回放容器使用 `replay` profile，不会随默认环境自动执行。

启动一次数据回放：

```bash
docker compose --profile replay up data-replay --build
```

临时指定回放条数和速率：

```bash
docker compose --profile replay run --rm -e ROW_LIMIT=20 -e REPLAY_RATE=10 data-replay
```

常用环境变量：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `BACKEND_INGEST_URL` | 后端订单注入接口 | `http://backend-api:8000/api/v1/stream/ingest` |
| `DATASET_PATH` | CSV 数据集路径 | `data_producer/dataset/DataCoSupplyChainDataset.csv` |
| `ROW_LIMIT` | 本次最多尝试发送行数 | `100` |
| `START_OFFSET` | 从 CSV 第几行开始发送 | `0` |
| `REPLAY_RATE` | 每秒发送行数 | `5` |
| `REQUEST_TIMEOUT_SECONDS` | 单次请求超时时间 | `5` |

本地直接运行回放脚本：

```bash
cd supply-chain-ai-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r data_producer/requirements.txt
ROW_LIMIT=10 REPLAY_RATE=5 python data_producer/replay_script.py
```

## 核心接口

### 后端健康检查

```http
GET /health
```

示例响应：

```json
{
  "status": "ok",
  "environment": "docker",
  "model_mode": "remote"
}
```

### 注入订单数据

```http
POST /api/v1/stream/ingest
```

支持标准字段，也兼容 DataCo 原始字段名，例如 `Order Id`、`Order Item Total`、`Late_delivery_risk`。

示例请求：

```json
{
  "order_id": "ORD-10023",
  "order_date": "2026-05-25 10:00:00",
  "shipping_mode": "Standard Class",
  "customer_city": "Los Angeles",
  "customer_country": "United States",
  "latitude": 34.0522,
  "longitude": -118.2437,
  "order_amount": 1500.0,
  "profit_ratio": -0.2,
  "late_delivery_risk": true
}
```

示例响应：

```json
{
  "status": "success",
  "order_id": "ORD-10023",
  "risk_score": 0.98,
  "is_high_risk": true,
  "alert": {
    "id": 1,
    "order_id": "ORD-10023",
    "risk_type": "高延迟风险",
    "probability": 0.98,
    "status": 0,
    "timestamp": "2026-05-25T10:00:00"
  }
}
```

### 实时 KPI

```http
GET /api/v1/kpi/realtime
```

返回字段包括：

- `totalOrders`
- `gmv`
- `otdRate`
- `riskCount`
- `delayRate`
- `heatMap`

### 历史趋势

```http
GET /api/v1/kpi/history?hours=24
```

### 最近告警

```http
GET /api/v1/alerts/recent?limit=50
```

### WebSocket 告警通道

```text
ws://localhost/api/v1/ws/alerts
```

后端推送两类消息：

```json
{
  "type": "stats",
  "data": {
    "totalOrders": 120,
    "gmv": 45000.5,
    "otdRate": 94.2,
    "riskCount": 6,
    "delayRate": 5.8,
    "heatMap": []
  }
}
```

```json
{
  "type": "alert",
  "data": {
    "id": 105,
    "orderId": "ORD-10023",
    "riskType": "高延迟风险",
    "probability": 0.89,
    "level": "danger",
    "icon": "fas fa-exclamation-circle",
    "timestamp": "2026-05-25T10:05:00"
  }
}
```

## 本地开发

### 后端

后端本地开发需要 Python 3.10+。不使用 Docker 时默认使用 `backend_api/dev.db` 作为 SQLite 开发库。

```bash
cd supply-chain-ai-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r backend_api/requirements.txt
uvicorn backend_api.app.main:app --reload --port 8000
```

### 前端

Vite 已配置 `/api` 代理到本地后端 `http://localhost:8000`，WebSocket 也走 `/api/v1/ws/alerts`。

```bash
cd supply-chain-ai-dashboard/frontend_ui/frontend_ui_v1
npm install
npm run dev
```

## 当前进度

已完成：

- 后端 FastAPI 基础框架。
- MySQL `orders`、`alerts` 基础表结构与自动建表。
- Redis KPI 缓存与告警发布适配。
- AI 微服务调用适配。
- CSV 数据回放脚本。
- WebSocket `stats` 和 `alert` 消息推送。
- Docker Compose 统一部署。
- Nginx 代理 `/api` 和 WebSocket Upgrade。

下一步建议：

- 增加告警去重，避免重复回放同一订单导致重复告警。
- 增加 `PATCH /api/v1/alerts/{id}/ack` 告警确认接口。
- 补齐物流热力图线路/节点 API。
- 增加 API 自动化测试。
- 统一 AI 模型训练与推理环境的 Scikit-learn 版本。
- 前端完成真实 WebSocket 数据的端到端展示验收。

## 文档

- 产品需求文档：`supply-chain-ai-dashboard/docs/PRD.md`
- 软件设计文档：`supply-chain-ai-dashboard/docs/SDD.md`
- Docker 部署说明：`supply-chain-ai-dashboard/docs/deployment.md`
- 后端后续任务：`supply-chain-ai-dashboard/backend_api/backend_next_steps.md`
