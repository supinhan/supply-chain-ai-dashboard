# 软件设计文档 (SDD)：AI 赋能企业供应链可视化分析系统 (MVP 版)

## 1. 引言

### 1.1 编写目的

本文档基于《产品需求文档 (PRD)：AI 赋能企业供应链可视化分析系统 (MVP 版)》编写，旨在从技术实现的角度，详细描述系统的软件架构、核心模块划分、数据结构与接口设计。本文档将作为后端开发工程师、前端开发工程师以及算法工程师进行编码和部署的直接依据。

### 1.2 系统范围

本项目 MVP 阶段包含三大核心模块：

1. **数据工程与流处理**：使用独立脚本读取 Kaggle 数据集，模拟真实业务高并发环境将时序数据打入后端。
2. **AI 智能预警**：基于机器学习模型对物流链路状态和异常延迟进行毫秒级在线推理和打分。
3. **可视化监控大屏**：实时展示 KPI、物流热力图及滚动告警列表的大屏应用。

---

## 2. 总体架构设计

### 2.1 系统逻辑架构

系统采用前后端分离的微服务雏形架构，分为数据层、逻辑层和表现层。

```mermaid
graph TD
    subgraph 表现层 前端大屏
        Dashboard[Vue 3 大屏界面]
        Map[ECharts 物流热力地图]
        WebSocketClient[WebSocket 客户端]
    end

    subgraph 逻辑层 后端服务 FastAPI
        API[RESTful API & WebSocket]
        ModelRunner[AI 模型推理引擎 (Scikit-learn/Pandas)]
        IngestController[数据注入控制器]
    end

    subgraph 数据层 存储设施
        MySQL[(MySQL 关系型数据库)]
        Redis[(Redis 高性能缓存)]
    end

    subgraph 外部数据源
        Script[Python 回放引擎 (读取 CSV)]
    end

    Script -- HTTP POST --> IngestController
    IngestController --> API
    IngestController --> ModelRunner
    API -- 存取 --> MySQL
    API -- 存取/发布订阅 --> Redis
    ModelRunner -- 风险告警 --> API
    API -- WebSocket 推送 --> WebSocketClient
    Dashboard -- HTTP GET --> API
```

### 2.2 技术栈选型

基于 PRD 约束（DC-01 至 DC-05），系统技术栈如下：

- **前端开发**：Vue 3 + Vite + ECharts (大屏地图/折线图)
- **后端开发**：Python 3.10+ + FastAPI (异步支持极佳，适合 WebSockets 和高并发)
- **算法模型**：Scikit-learn, Pandas (预训练模型导出为 `.pkl`)
- **数据存储**：MySQL 8.0 (持久化业务数据), Redis 7.0 (高频 KPI 缓存、消息队列)
- **容器编排**：Docker + Docker Compose

---

## 3. 核心模块详细设计

### 3.1 数据回放与注入模块

- **设计思路**：独立于主系统的 Python 脚本 `replay_engine.py`。
- **执行流程**：
  1. 通过 Pandas 加载 `DataCoSupplyChainDataset.csv`。
  2. 根据设定的倍率（如1秒=业务1小时）计算等待时间并 `time.sleep()`。
  3. 通过 HTTP `requests.post()` 将单条行数据转 JSON 并发送给 FastAPI 后端。

### 3.2 AI 智能推理服务模块

- **设计思路**：在 FastAPI 启动生命周期（Lifespan）时，预加载 `risk_model.pkl` 至内存，避免每次请求重复加载。
- **执行流程**：
  1. 接收到单条 JSON 订单数据后，提取所需特征。
  2. 调用 `model.predict_proba()` 输出风险概率分值。
  3. 若得分 > 0.85，生成 `Alert` 对象持久化到 MySQL，并推送至 Redis Pub/Sub（或直接发往 WebSocket 连接池）。

### 3.3 可视化监控大屏模块

- **设计思路**：响应式全屏大屏，分为左中右三个区域。
- **前端状态管理**：由于数据主要靠后端推拉，考虑使用 `Pinia` 管理全局 Socket 连接实例、最新的告警列表（限制最大展示长度，如前 50 条防 OOM）和实时聚合 KPI 数据。降采样处理通过定时截流（Throttle）在 ECharts 层面进行。

---

## 4. 数据库与存储设计

### 4.1 关系型数据库 (MySQL)

设计核心表如下：

**表1：orders (订单表)**
| 字段名 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, Auto_Inc | 主键ID |
| order_id | VARCHAR(64) | Unique | 原始订单号 |
| order_date | DATETIME | - | 订单生成时间 |
| customer_city | VARCHAR(128) | - | 客户城市 |
| latitude | DECIMAL(10,6)| - | 纬度 |
| longitude | DECIMAL(10,6)| - | 经度 |
| order_amount | DECIMAL(10,2)| - | 订单金额 |
| risk_score | DECIMAL(5,4) | - | AI预测风险概率 (0.00-1.00) |
| created_at | DATETIME | DEFAULT NOW()| 接收时间 |

**表2：alerts (风险告警表)**
| 字段名 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK, Auto_Inc | 告警ID |
| order_id | VARCHAR(64) | FK | 关联订单号 |
| risk_type | VARCHAR(64) | - | 风险类型（如：延迟交付）|
| probability| DECIMAL(5,4) | - | 触发时的风险概率 |
| status | TINYINT | - | 0-未确认，1-已确认 |
| created_at | DATETIME | DEFAULT NOW()| 告警生成时间 |

### 4.2 缓存与中间件 (Redis)

- **KPI 聚合缓存 (String/Hash)**：
  - Key: `kpi:realtime:dashboard`
  - Value: `{"total_orders": 1205, "total_gmv": 54300.5, "risk_count": 12}`
  - 更新策略：后端每接收一笔订单更新一次（可利用 Pipeline 批量更新），前端轮询或 WebSocket 推送拉取。
- **消息队列 (Pub/Sub)**：
  - Topic: `alerts:channel`
  - 用于 FastAPI 多 Worker 进程间的 WebSocket 告警广播。

---

## 5. 接口设计 (API)

### 5.1 HTTP RESTful API

**1. 数据注入接口**

- **路径**：`POST /api/v1/stream/ingest`
- **入参**：
  
  ```json
  {
      "order_id": "ORD-10023",
      "order_date": "2023-10-01 10:00:00",
      "customer_city": "Los Angeles",
      "latitude": 34.0522,
      "longitude": -118.2437,
      "order_amount": 1500.00
  }
  ```
- **出参**：`{"status": "success", "risk_score": 0.05}`

**2. 获取历史进出货趋势**

- **路径**：`GET /api/v1/kpi/history?hours=24`
- **出参**：返回按时间维度聚合的折线图数据。

### 5.2 WebSocket API

**1. 风险告警推送通道**

- **地址**：`ws://domain/api/v1/ws/alerts`
- **机制**：前端建立连接后，保持监听。一旦有高风险订单产生，后端主动下推数据。
- **推送报文示例**：
  
  ```json
  {
      "type": "NEW_ALERT",
      "data": {
          "alert_id": 105,
          "order_id": "ORD-10023",
          "risk_type": "高延迟风险",
          "probability": 0.89,
          "timestamp": "2026-05-14T10:05:00"
      }
  }
  ```

---

## 6. 部署架构设计 (Docker Compose)

为满足一键演示需求 (QR-05)，项目根目录需提供 `docker-compose.yml`，编排以下服务：

1. **mysql-db**: MySQL 容器，映射端口 3306，挂载初始化 SQL 脚本至 `/docker-entrypoint-initdb.d` 用于建库建表。
2. **redis-cache**: Redis 容器，映射端口 6379。
3. **backend-api**: 基于 `python:3.10-slim` 构建的 FastAPI 容器，启动命令为 `uvicorn main:app --host 0.0.0.0 --port 8000`。映射端口 8000。依赖 mysql 与 redis 启动。
4. **frontend-dashboard**: 基于 Nginx 构建的 Vue 3 静态资源容器。打包后代理转发 `/api` 到 `backend-api:8000`。
5. **data-replay** (可选/手动): 数据回放脚本容器，可在其它容器就绪后执行一次性任务或后台常驻执行。

项目启动命令：

```bash
docker-compose up -d --build
```

启动后通过访问 `http://localhost` 即可进入系统主界面。
