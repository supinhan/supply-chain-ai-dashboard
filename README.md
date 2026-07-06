# AI 赋能企业供应链可视化分析系统

本项目是一个供应链可视化与智能预警系统。系统使用 Kaggle DataCo 供应链数据集模拟实时订单流，通过后端服务调用 AI 风险模型完成在线评分，并将实时 KPI 与高风险告警推送到前端大屏。

### 基础闭环数据流
```text
DataCo CSV 回放 -> FastAPI 后端接收 -> AI 风险评分 -> MySQL/Redis 写入 -> WebSocket 推送 -> Vue 大屏展示
```

---

## 目录
- [1. 功能概览](#1-功能概览)
- [2. 技术栈](#2-技术栈)
- [3. 项目结构](#3-项目结构)
- [4. 本地运行与开发指南](#4-本地运行与开发指南)
  - [方法 A：Docker Compose 一键运行（推荐，包含完整中间件）](#方法-adocker-compose-一键运行推荐包含完整中间件)
  - [方法 B：分进程手动启动（免 Docker 部署，使用 SQLite 临时数据库）](#方法-b分进程手动启动免-docker-部署使用-sqlite-临时数据库)
- [5. 服务器部署指南 (VPS)](#5-服务器部署指南-vps)
  - [方案 A：全栈云端单机部署](#方案-a全栈云端单机部署)
  - [方案 B：跨网段混合部署（服务器端前/后端 + 本地端 AI 与数据推送）](#方案-b跨网段混合部署服务器端前后端--本地端-ai-与数据推送)
- [6. 数据回放说明](#6-数据回放说明)
- [7. 核心接口与数据契约](#7-核心接口与数据契约)
- [8. 核心文档指引](#8-核心文档指引)

---

## 1. 功能概览

- **数据回放**：从 `DataCoSupplyChainDataset.csv` 读取订单数据，按指定速率和配置行数注入后端。
- **订单接入**：后端提供 `POST /api/v1/stream/ingest` 接口接收实时订单流，支持 HMAC-SHA256 签名鉴权。
- **AI 风险评分**：后端调用独立 AI 微服务 `/predict/risk`，实时返回风险发生概率与可解释性归因（XAI）。
- **实时告警推送**：对高风险订单生成告警，通过 WebSocket 实时推送到前端大屏。
- **未来销量预测**：提供 `/api/v1/forecast` 接口预测未来 7 天销量，在 AI 服务故障时支持历史数据 fallback 兜底。
- **KPI 可视化大屏**：直观展示累计订单量、GMV 销售总额、OTD 准时交货率、延迟风险占比和全球物流城市热力图。

---

## 2. 技术栈

| 模块 | 技术选型 |
| --- | --- |
| **前端大屏** | Vue 3 (Composition API), Vite, ECharts 5.x, Nginx |
| **后端 API** | Python 3.10+, FastAPI, SQLAlchemy, Uvicorn |
| **AI 算法服务** | Python, Scikit-learn (Random Forest & ANN), SHAP (XAI) |
| **数据存储与缓存** | MySQL 8.0, Redis 7.0 |
| **数据回放引擎** | Python 3, CSV, Requests |
| **容器化与部署** | Docker, Docker Compose |

---

## 3. 项目结构

```text
.
├── README.md                            # 本文档
└── supply-chain-ai-dashboard/           # 项目主目录
    ├── docker-compose.yml               # 统一容器编排入口
    ├── ai_algorithms/
    │   └── supplychain-ai-service/      # AI 推理微服务与训练模型
    ├── backend_api/                     # FastAPI 后端服务
    │   ├── app/
    │   │   ├── api/                     # 路由与控制器 (REST & WebSocket)
    │   │   ├── core/                    # 全局配置与签名校验
    │   │   ├── db/                      # ORM 模型与数据库连接
    │   │   └── services/                # Redis、AI 容灾调用等核心服务
    │   └── requirements.txt
    ├── data_producer/                   # 数据回放引擎与 Kaggle 原始数据集
    ├── docs/                            # 需求、设计、测试与管理文档
    ├── frontend_ui/
    │   └── frontend_ui_v1/              # Vue 3 大屏前端项目
    └── test/                            # 系统测试用例及自动化测试脚本
```

---

## 4. 本地运行与开发指南

本地运行前，请先进入应用主目录：
```bash
cd supply-chain-ai-dashboard
```

### 方法 A：Docker Compose 一键运行（推荐，包含完整中间件）
此方式会自动构建所有环境并启动 MySQL 和 Redis 容器，一键跑通闭环。

1. **构建并拉起底层服务环境**：
   ```bash
   docker compose up -d --build
   ```
2. **启动数据回放流注入**：
   ```bash
   docker compose --profile replay up data-replay --build
   ```
3. **本地访问地址**：
   - 前端大屏：`http://localhost`
   - 后端 Swagger API：`http://localhost:8000/docs`
   - AI 服务 Swagger API：`http://localhost:8081/docs`

---

### 方法 B：分进程手动启动（免 Docker 部署，使用 SQLite 临时数据库）
该模式下后端会自动降级为本地 SQLite `dev.db`，免去 MySQL/Redis 依赖。

#### Windows 本地启动步骤
请打开 4 个独立的 PowerShell 终端分别执行以下进程：

1. **终端 1：启动后端 API 服务 (端口: 8000)**
   ```powershell
   # 创建虚拟环境并使用其中的 pip 安装依赖
   python -m venv .venv
   .\.venv\Scripts\pip.exe install -r backend_api/requirements.txt
   
   # 启动服务 (通过虚拟环境中的 python 启动，免受脚本执行策略限制)
   .\.venv\Scripts\python.exe -m uvicorn backend_api.app.main:app --reload --port 8000
   ```

2. **终端 2：启动 AI 推理服务 (端口: 8081)**
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn ai_algorithms.supplychain-ai-service.api:app --reload --port 8081
   ```

3. **终端 3：启动前端 Vue 大屏 (端口: 5173)**
   ```powershell
   cd frontend_ui/frontend_ui_v1
   npm install
   npm run dev
   ```
   *启动后访问：`http://localhost:5173`。*

4. **终端 4：启动本地时序数据回放**
   ```powershell
   # 可选：设置环境变量（默认发送 100 条，每秒 5 条）
   $env:ROW_LIMIT="100"
   $env:REPLAY_RATE="5"
   .\.venv\Scripts\python.exe data_producer/replay_script.py
   ```

---

#### Linux / macOS 本地启动步骤
请打开 4 个独立的 Terminal 终端分别执行以下进程：

1. **终端 1：启动后端 API 服务 (端口: 8000)**
   ```bash
   # 创建、激活虚拟环境并安装依赖
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend_api/requirements.txt
   
   # 启动服务
   uvicorn backend_api.app.main:app --reload --port 8000
   ```

2. **终端 2：启动 AI 推理服务 (端口: 8081)**
   ```bash
   source .venv/bin/activate
   uvicorn ai_algorithms.supplychain-ai-service.api:app --reload --port 8081
   ```

3. **终端 3：启动前端 Vue 大屏 (端口: 5173)**
   ```bash
   cd frontend_ui/frontend_ui_v1
   npm install
   npm run dev
   ```
   *启动后访问：`http://localhost:5173`。*

4. **终端 4：启动本地时序数据回放**
   ```bash
   source .venv/bin/activate
   # 可选：设置环境变量
   export ROW_LIMIT="100"
   export REPLAY_RATE="5"
   python data_producer/replay_script.py
   ```


---

## 5. 服务器部署指南 (VPS)

服务器部署通常面向公网，推荐使用 Docker Compose 快速运行。

### 方案 A：全栈云端单机部署
将前端、后端、AI 算法、数据库及数据回放均放在同一台公网服务器上。

1. 在服务器克隆仓库并进入主目录：
   ```bash
   cd supply-chain-ai-dashboard
   ```
2. 拷贝配置环境变量（包含密钥和数据库端口映射）：
   ```bash
   cp .env.example .env
   ```
3. 构建并后台运行所有容器：
   ```bash
   docker compose up -d --build
   ```
4. 开放服务器的 `80` 端口，通过 `http://<服务器_公网IP>` 即可打开供应链智能看板。

---

### 方案 B：跨网段混合部署（服务器端前/后端 + 本地端 AI 与数据推送）
当服务器（VPS）算力有限或为了保护本地模型资产时，可采用本方案。

```text
[ 本地 PC ]                                            [ 云端 VPS ]
- AI 算法推理 (Port 8081)  ----(内网穿透 / mTLS)---->  - Nginx 反向代理 (Port 80)
- 时序数据回放 (HMAC签名)  ---(公网网络数据注入)---->  - FastAPI 后端 (Port 8000)
                                                       - MySQL / Redis 中间件
```

#### 1. 服务器端配置 (VPS 侧)
1. 配置 VPS 侧的 `.env` 环境变量，开启 HMAC 时间戳校验与接口防篡改：
   ```bash
   INGEST_API_KEY="vps-client-key"
   INGEST_HMAC_SECRET="vps-long-random-secret"
   
   # 填写本地 AI 推理服务的公网穿透域名或 IP 地址
   AI_SERVICE_URL="http://<本地AI穿透公网URL>"
   AI_SERVICE_API_KEY="ai-client-key"
   AI_SERVICE_HMAC_SECRET="ai-long-random-secret"
   ```
2. 启动服务端所需基础容器（可根据需要停止或去除本地 `ai-service` 容器）：
   ```bash
   docker compose up -d --build
   ```

#### 2. 本地侧配置 (本地 PC 设备)
1. **AI 服务穿透**：本地运行 AI 服务并开启 `8081` 端口，通过穿透工具（如 `frp`、`ngrok` 或 `Cloudflare Tunnel`）映射出公网可访问的 HTTPS 域名，填入 VPS 的 `AI_SERVICE_URL` 中。
2. **时序数据推送**：本地执行回放数据发送脚本，并将其指向 VPS 服务器的公网接入 IP：
   ```bash
   # 配置推送到 VPS 的公网接口和认证凭证
   export BACKEND_INGEST_URL="http://<VPS_IP>:8000/api/v1/stream/ingest"
   export INGEST_API_KEY="vps-client-key"
   export INGEST_HMAC_SECRET="vps-long-random-secret"
   
   # 执行本地数据推送
   python data_producer/replay_script.py
   ```
   数据由本地回放引擎签名后，通过公网安全地投递给 VPS 上的 backend-api。服务端进行验签，并反向调用本地穿透出的 AI 服务进行打分，打分结果存入 MySQL 并通过 Redis 广播到大屏上，完成安全联调闭环。

---

## 6. 数据回放说明

数据回放可以通过 Docker 或本地直接运行。常用环境变量配置如下：

| 环境变量 | 作用说明 | 默认值 |
| --- | --- | --- |
| `BACKEND_INGEST_URL` | 后端订单注入接口 | `http://backend-api:8000/api/v1/stream/ingest` |
| `DATASET_PATH` | CSV 数据集路径 | `data_producer/dataset/DataCoSupplyChainDataset.csv` |
| `ROW_LIMIT` | 本次最多尝试发送的订单行数 | `100` |
| `START_OFFSET` | 从 CSV 数据集的第几行开始发送 | `0` |
| `REPLAY_RATE` | 每秒发送的订单条数 | `5` |
| `REQUEST_TIMEOUT_SECONDS` | 单次网络请求超时时间 | `5` |

---

## 7. 核心接口与数据契约

### 7.1 后端健康检查
- **请求方法**：`GET`
- **路径**：`/health`
- **示例响应**：
  ```json
  {
    "status": "ok",
    "environment": "docker",
    "model_mode": "remote"
  }
  ```

### 7.2 注入订单数据
- **请求方法**：`POST`
- **路径**：`/api/v1/stream/ingest`
- **安全请求头（选填）**：
  - `X-SCAI-API-Key`: 客户端凭证 Key
  - `X-SCAI-Timestamp`: 当前 Unix 时间戳
  - `X-SCAI-Signature`: HMAC-SHA256 签名串（防篡改）
- **请求体 (Request Body)**：
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
- **示例响应**：
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

---

## 8. 核心文档指引

- **系统测试报告**：[测试计划与用例报告.md](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/测试计划与用例报告.md) (及 [系统测试文档.pdf](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/系统测试文档.pdf))
- **产品需求文档 (PRD)**：[需求分析文档.docx](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/需求分析文档.docx) (及 [需求分析文档.pdf](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/需求分析文档.pdf))
- **软件设计文档 (SDD)**：[软件设计文档.docx](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/软件设计文档.docx) (及 [软件设计文档.pdf](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/软件设计文档.pdf))
- **任务分工文档**：[任务分工.md](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/任务分工.md) 与 [项目管理文档.md](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/项目管理文档.md)
- **Docker 统一部署指南**：[deployment.md](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/docs/deployment.md)
