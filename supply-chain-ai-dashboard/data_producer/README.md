# 数据回放引擎 (Data Replay Engine)

本模块负责从 Kaggle 真实供应链数据集 `DataCoSupplyChainDataset.csv` 中流式读取订单记录，并按照设定的速率通过安全 HMAC 签名加密发送给后端接入 API。

## 📂 目录结构

```text
data_producer/
├── dataset/
│   └── DataCoSupplyChainDataset.csv  # Kaggle 供应链数据集（需要下载并放置于此）
├── Dockerfile                        # 容器化构建配置文件
├── requirements.txt                  # Python 依赖包 (requests)
└── replay_script.py                  # 核心流式回放与断点续传控制脚本
```

---

## ⚙️ 环境变量配置

在启动回放脚本前，可以通过设置以下环境变量来控制回放的行为：

| 环境变量 | 默认值 | 作用说明 |
| :--- | :--- | :--- |
| `BACKEND_INGEST_URL` | `http://backend-api:8000/api/v1/stream/ingest` | 目标后端订单接入接口地址 |
| `DATASET_PATH` | `data_producer/dataset/DataCoSupplyChainDataset.csv` | CSV 数据集文件的相对/绝对路径 |
| `ROW_LIMIT` | `100` | 本次运行最大发送订单行数 (防止耗尽全部 18 万条) |
| `START_OFFSET` | `0` | 发送的起始 CSV 行号 (无 checkpoint 时使用) |
| `REPLAY_RATE` | `5` | 发送速率（每秒发送多少条订单数据） |
| `REQUEST_TIMEOUT_SECONDS` | `5` | HTTP 请求超时时间（秒） |
| `INGEST_API_KEY` | `""` | 保护后端入口的 API Key (留空则关闭校验) |
| `INGEST_HMAC_SECRET` | `""` | 保护后端入口的 HMAC-SHA256 签名密钥 (留空则关闭校验) |

---

## 🚀 启动回放

### 1. 本地独立运行
在配置好 Python 虚拟环境并安装 `requests` 依赖后，可以在本地直接运行：
```bash
# Windows 设置临时配置并执行
$env:BACKEND_INGEST_URL="http://127.0.0.1:8000/api/v1/stream/ingest"
$env:INGEST_API_KEY="test-key"
$env:INGEST_HMAC_SECRET="test-secret"
$env:ROW_LIMIT=20
$env:REPLAY_RATE=5

python data_producer/replay_script.py
```

### 2. 通过 Docker Compose 启动 (VPS/生产环境)
在主目录下通过 `replay` profile 进行一键回放启动：
```bash
docker compose --profile replay up data-replay --build
```
或者临时修改回放限制并启动：
```bash
docker compose --profile replay run --rm -e ROW_LIMIT=50 -e REPLAY_RATE=10 data-replay
```

---

## 🛡️ 断点续传与安全机制

1. **断点续传**：脚本运行时会自动在 `runtime/` 目录下生成 `replay_checkpoint.json`，记录最后成功投递的 CSV 行号与订单 ID。当网络中断或进程异常重启时，脚本会自动读取 checkpoint 并实现无缝续传。
2. **安全签名**：当配置了 `INGEST_HMAC_SECRET` 时，脚本会对每个 HTTP Post Body、时间戳以及方法路径进行 HMAC-SHA256 签名计算，并携带 `X-SCAI-Signature` 与时间戳 header。后端会对时间窗口及签名合法性进行双向校验，防范非法篡改与重放攻击。
