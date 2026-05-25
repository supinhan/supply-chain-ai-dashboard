# 后端后续任务清单与项目协作规划

## 1. 当前后端骨架已覆盖

- FastAPI 主服务入口：`backend_api/app/main.py`，旧入口 `backend_api/main.py` 保留兼容。
- API 路由层：`backend_api/app/api/routes.py`
- 配置层：`backend_api/app/core/config.py`
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

### P0 必须完成

- 数据回放联调：完成 `data_producer/replay_script.py`，读取 DataCo CSV 后 POST 到 `/api/v1/stream/ingest`。
- AI 服务联调：确认独立 AI 微服务 `/predict/risk` 入参/出参与主后端 `model_runner.py` 一致。
- 前端 WebSocket 联调：当前已改为自动连接当前站点 `/api/v1/ws/alerts`，下一步需要和真实后端广播做端到端验证。
- 数据库验收：用 MySQL 启动后验证 `orders`、`alerts` 表自动建表和写入。
- 端到端演示链路：CSV 回放 -> 后端入库 -> AI 打分 -> 高风险告警 -> 前端列表闪烁。

### P1 应尽快补齐

- Redis KPI 缓存：当前已写入 `kpi:realtime:dashboard`，后续需将读取链路改为优先读 Redis、失效时回源 MySQL。
- Redis Pub/Sub：当前已发布到 `alerts:channel`，后续需补后台订阅任务，支持多 Worker 或多实例广播。
- 告警确认接口：新增 `PATCH /api/v1/alerts/{id}/ack`，支撑 Alert 状态流转。
- 物流热力图接口：新增当前在途订单的线路/节点 API，给 ECharts 地图使用。
- API 自动化测试：覆盖 ingest、kpi、history、alerts、WebSocket 基础连接。
- Docker 启动验收：在干净环境执行 `docker compose up -d --build`，确认 5 个核心服务健康。

### P2 增强项

- 历史趋势按业务订单时间聚合，而不是按后端接收时间聚合。
- 增加限流、批量注入接口和错误数据落库表。
- 增加结构化日志、请求追踪 ID、基础 Prometheus 指标。
- 将前端需要的 forecast 数据从静态 mock 改成后端/AI 服务接口。

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
