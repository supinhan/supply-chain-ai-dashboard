# 后端后续任务清单与项目协作规划

## 1. 当前后端骨架已覆盖

- FastAPI 主服务入口：`backend_api/app/main.py`，旧入口 `backend_api/main.py` 保留兼容。
- API 路由层：`backend_api/app/api/routes.py`
- 配置层：`backend_api/app/core/config.py`
- 接口安全工具：`backend_api/app/core/security.py`
- 数据模型与数据库访问层：`backend_api/app/db/database.py`
- AI 推理适配层：`backend_api/app/services/model_runner.py`
- Redis 缓存与 Pub/Sub 适配层：`backend_api/app/services/cache.py`
- WebSocket 连接管理：`backend_api/app/ws/manager.py`
- 请求/响应 Schema：`backend_api/app/schemas.py`
- 统一部署文件：根目录 `docker-compose.yml`、`.env.example`、`.dockerignore`
- 服务镜像文件：`backend_api/Dockerfile`、`frontend_ui/frontend_ui_v1/Dockerfile`、`data_producer/Dockerfile`、`ai_algorithms/supplychain-ai-service/Dockerfile`

## 2. Docker 与部署约定

- 统一从项目根目录运行 `docker compose up -d --build`。
- 前端访问入口为 `http://localhost`，Nginx 代理 `/api` 与 `/api/v1/ws/alerts` 到后端。
- 后端容器通过 `AI_SERVICE_URL=http://ai-service:8000` 调用算法微服务。
- AI 服务不再单独维护独立 compose，子目录 `docker-compose.yml` 只保留迁移提示。
- 数据回放容器使用 `replay` profile，执行 `docker compose --profile replay up data-replay --build`。
- 详细命令见 `docs/deployment.md`。

## 3. 下一步开发任务

### 已完成的二轮对接

- 数据回放脚本已支持读取 DataCo CSV、字段裁剪、失败重试、指数退避、断点续跑和失败订单日志。
- AI 风险评分已支持远程 AI 服务优先、失败时本地模型/启发式 fallback。
- 高风险告警已保存 XAI 归因到 `alerts.detail`，并通过 REST 与 WebSocket 返回给前端。
- `/api/v1/forecast` 已完成，优先调用 AI 服务，失败时使用后端历史数据生成 7 天 fallback。
- DataCo 目的地、订单状态、数量、计划运输天数字段已映射、入库，并用于 KPI 和热力图聚合。
- 后端测试已覆盖字段映射、订单入库、热力图聚合、XAI 告警和 forecast fallback。

### P0 当前优先级

- 接口安全：已加入数据回放 -> 后端 ingest、后端 -> AI 服务的 API key/HMAC 签名能力；下一步是为生产环境生成强随机密钥并做 Docker 端到端验收。
- Docker 启动验收：在干净环境执行 `docker compose up -d --build`，确认 MySQL、Redis、AI 服务、后端、前端全部健康。
- 数据回放端到端验收：执行 `docker compose --profile replay up data-replay --build`，确认 CSV 回放 -> 后端入库 -> AI 打分 -> 高风险告警 -> 前端更新。

### P1 应尽快补齐

- 登录与鉴权：新增用户表、登录接口、JWT/session 鉴权依赖，前端未登录跳转 `/login`。
- 可靠投递：引入服务端 ACK、幂等投递审计、本地 pending 队列重放，以及失败订单人工/自动重放流程。
- Redis KPI 缓存：当前已写入 `kpi:realtime:dashboard`，后续需将读取链路改为优先读 Redis、失效时回源 MySQL。
- Redis Pub/Sub：当前已发布到 `alerts:channel`，后续需补后台订阅任务，支持多 Worker 或多实例广播。
- 告警确认接口：新增 `PATCH /api/v1/alerts/{id}/ack`，支撑 Alert 状态流转。
- 物流热力图接口：新增当前在途订单的线路/节点 API，给 ECharts 地图使用。
- API 自动化测试：继续补充 WebSocket 基础连接、鉴权失败、可靠投递和告警状态流转测试。
- 数据库迁移治理：接入 Alembic，替代 `create_all` 与启动时手写补列。

### P2 增强项

- 历史趋势按业务订单时间聚合，而不是按后端接收时间聚合。
- Forecast fallback 改为按业务订单时间、销售额和数量聚合，不只按接收时间订单数均值。
- 增加限流、批量注入接口和错误数据落库表。
- 增加结构化日志、请求追踪 ID、基础 Prometheus 指标。
- 如果部署条件允许，进一步加入 HTTPS、mTLS 或安全隧道，减少明文内网传输风险。

## 4. 与其他角色对接方式

- 与前端对接：约定 WebSocket 消息格式为 `type=stats` 和 `type=alert`；前端只关心 `stats.data` 与 `alert.data`。
- 与 AI 算法对接：主后端默认调用 `AI_SERVICE_URL/predict/risk`，入参包含 `order_id`、`order_amount`、`profit_ratio`、`shipping_mode`。
- 与数据工程对接：回放脚本可以直接发送 DataCo 原始字段名，后端已兼容 `Order Id`、`Order Item Total`、`Late_delivery_risk` 等字段。
- 与测试/答辩对接：每次联调保留一组固定高风险样本，确保演示时稳定触发告警。

## 5. 一个月项目规划

- Week 1：环境与数据链路。完成 Docker Compose、MySQL/Redis、CSV 回放脚本和 ingest API。
- Week 2：AI 与后端主流程。完成 AI 微服务联调、风险评分、告警落库、WebSocket 推送。
- Week 3：前端大屏联调。完成 KPI、预警列表、热力图接口与前端动态渲染。
- Week 4：验收与演示。做端到端压测、异常数据测试、演示脚本、答辩材料和视频录制。
