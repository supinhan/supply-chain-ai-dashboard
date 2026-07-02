# AI 赋能企业供应链可视化分析系统

本项目是一个供应链可视化与智能预警系统。系统使用 Kaggle DataCo 供应链数据集模拟实时订单流，通过后端服务调用 AI 风险模型完成在线评分，并将实时 KPI 与高风险告警推送到前端大屏。

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
    ├── docs/                            # 需求分析/软件设计文档、系统测试报告、部署指南等
    ├── frontend_ui/
    │   └── frontend_ui_v1/              # Vue 3 可视化大屏
    ├── test/                            # 19 项系统集成与测试用例目录
    └── docker-compose.yml               # 统一服务编排入口
```

## 快速启动

进入应用主目录：

```bash
cd supply-chain-ai-dashboard
```

配置环境变量文件（项目内置了默认配置，如需修改请手动创建并配置 `.env` 文件，如开启 HMAC 验证）：

```bash
# 默认本地开发无需配置 .env 即可快速启动
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

清理数据库 volume 并重置演示：

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

## 本地开发与操作说明

### 1. 运行环境准备
本地开发需要 Python 3.11+ 和 Node.js。不使用 Docker 时，后端默认使用 `backend_api/dev.db` 作为 SQLite 本地临时数据库，无需单独配置 MySQL/Redis，即开即用。

### 2. 启动本地服务进程

#### 后端 API 服务 (Port: 8000)
```bash
cd supply-chain-ai-dashboard
python -m venv .venv
# Windows 激活虚拟环境
.\.venv\Scripts\activate
# Linux/macOS 激活虚拟环境
# source .venv/bin/activate

pip install -r backend_api/requirements.txt
# 配置安全密钥环境变量（可选，默认为空关闭校验）
$env:INGEST_API_KEY="test-key"
$env:INGEST_HMAC_SECRET="test-secret"
$env:AI_SERVICE_URL="http://127.0.0.1:8081"
$env:AI_SERVICE_API_KEY="test-key"
$env:AI_SERVICE_HMAC_SECRET="test-secret"

uvicorn backend_api.app.main:app --reload --port 8000
```

#### AI 预测服务 (Port: 8081)
在相同的虚拟环境下，单独开启终端启动 AI 服务：
```bash
cd supply-chain-ai-dashboard
.\.venv\Scripts\activate

# 配置对应的 HMAC 验证安全密钥
$env:AI_SERVICE_API_KEY="test-key"
$env:AI_SERVICE_HMAC_SECRET="test-secret"

uvicorn ai_algorithms.supplychain-ai-service.api:app --reload --port 8081
```

#### 前端 Vue 看板大屏 (Port: 5173)
```bash
cd supply-chain-ai-dashboard/frontend_ui/frontend_ui_v1
npm install
npm run dev
```

### 3. 一键运行自动化测试套件
系统测试脚本已按照 19 项用例整齐划分存放在 `test/` 目录下。我们提供了一键测试运行器 `test/run_all.py`，它会自动并行/串行调度所有自动化用例，并在各自的用例目录下生成实际的运行日志 `result.log`：
```bash
cd supply-chain-ai-dashboard
# 确保后台已启动 backend_api(8000) 和 ai-service(8081)
python test/run_all.py
```

---

## 🌐 VPS 生产环境部署说明

在 VPS (如 Ubuntu/Debian 容器) 上进行统一部署时，推荐使用 Docker Compose，它能够自动拉起 MySQL 8.0、Redis 7.0、后端 API、Nginx 反向代理以及 Vue 编译静态资源。

### 1. 快速单机部署（全栈微服务均在 VPS）
在 VPS 服务器上 clone 仓库，进入主目录后执行：
```bash
cd supply-chain-ai-dashboard
# 复制并配置环境变量
cp .env.example .env
# 启动所有服务容器 (MySQL, Redis, AI, Backend, Frontend)
docker compose up -d --build
```
启动后，Nginx 会默认监听 VPS 的 `80` 端口。浏览器直接访问 `http://<VPS_IP>` 即可打开供应链智能看板。

---

## 🔀 混合部署方案（VPS 部署前端/后端 + 本地运行 AI 与数据推送）

在学校演示或企业实际业务中，由于 AI 模型体积较大、对算力要求高，或者为了保护模型资产，通常会将 **前端大屏与后端 API 部署在公网 VPS**，而将 **AI 推理和订单回放数据留在本地 PC/局域网设备运行**，将数据向公网推送。

### 1. 服务端配置 (VPS 侧)
1. 在 VPS 上修改 `docker-compose.yml`，我们仅需要启动 `mysql-db`, `redis-cache`, `backend-api`, 和 `frontend-dashboard` 即可。可以注释或移除 `ai-service` 容器的启动项。
2. 配置服务端的 `.env` 文件，开启 HMAC 安全密钥校验以保证公网传输安全：
   ```bash
   INGEST_API_KEY=vps-client-key
   INGEST_HMAC_SECRET=vps-long-random-secret
   
   # 本地 AI 推理服务的公网穿透/映射地址 (参见下方本地侧配置)
   AI_SERVICE_URL=http://<本地AI穿透公网IP或域名>
   AI_SERVICE_API_KEY=ai-client-key
   AI_SERVICE_HMAC_SECRET=ai-long-random-secret
   ```
3. 在 VPS 上启动服务端：
   ```bash
   docker compose up -d --build
   ```

### 2. 本地侧配置 (本地 PC / 局域网机房)
1. **AI 服务映射**：在本地 PC 启动 AI 预测服务（监听本地 8081），并使用穿透工具（如 `frp`, `ngrok` 或 `Cloudflare Tunnel`）将本地 `8081` 映射为公网可访问的 URL（即填入 VPS 服务端 `.env` 中 `AI_SERVICE_URL`）。
2. **数据回放推送**：在本地 PC 执行回放数据发送脚本，并将其指向 VPS 服务器的公网接入 IP：
   ```bash
   # 配置推送到 VPS 的公网接口和认证凭证
   export BACKEND_INGEST_URL="http://<VPS_IP>:8000/api/v1/stream/ingest"
   export INGEST_API_KEY="vps-client-key"
   export INGEST_HMAC_SECRET="vps-long-random-secret"
   
   # 执行本地流式数据推送
   python data_producer/replay_script.py
   ```
   数据被本地 producer 顺次读取并用 HMAC 签名后，通过公网安全地投递给 VPS 上的 backend-api。服务端进行验签，并反向调用本地穿透出的 AI 服务进行打分，打分结果存入 MySQL 并通过 Redis 广播到前端挂在大屏上，完成跨网段混合闭环！

---

## 📁 核心文档指引

- **系统测试报告**：[测试计划与用例报告.md](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/测试计划与用例报告.md) (及 [系统测试文档.pdf](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/系统测试文档.pdf))
- **产品需求文档 (PRD)**：[需求分析文档.docx](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/需求分析文档.docx) (及 [需求分析文档.pdf](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/需求分析文档.pdf))
- **软件设计文档 (SDD)**：[软件设计文档.docx](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/软件设计文档.docx) (及 [软件设计文档.pdf](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/软件设计文档.pdf))
- **Docker 统一部署指南**：[deployment.md](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/deployment.md)
