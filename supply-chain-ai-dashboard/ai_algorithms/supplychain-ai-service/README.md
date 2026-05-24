# Supply Chain AI Risk & Trend Prediction Service (MLOps)

本项目是供应链大系统中的 **AI 推理微服务** 模块。基于真实公开的全球供应链数据集 **Kaggle DataCoSupplyChainDataset**（包含约 18 万条真实多国工业订单记录），通过 MLOps 流程实现了数据清洗、特征数字化、多任务机器学习模型训练、带有 XAI（可解释性异常归因）的离线/在线推理服务，并最终通过 Docker 进行微服务容器化封装。

---

## 🛠️ 核心架构与技术栈
- **核心大脑**：Python 3.11 + Scikit-Learn（随机森林分类器 `RandomForestClassifier` & 随机森林回归器 `RandomForestRegressor`）
- **数据处理**：Pandas（支持 `ISO-8859-1` 拉丁语系国际化多国字符解码）+ NumPy
- **微服务接口**：FastAPI + Uvicorn + Pydantic 
- **容器化部署**：Docker + Docker Compose (多任务端口映射与服务编排)

---

## 📂 项目目录结构
```text
supplychain-ai-service/
├── data/
│   └── DataCoSupplyChainDataset.csv  # 从 Kaggle 下载的 18 万条真实供应链原始数据集
├── model/
│   ├── risk_model.pkl                # 训练好的风险拦截分类模型
│   ├── delay_model.pkl               # 训练好的延迟交付预测模型
│   ├── sales_model.pkl               # 训练好的销量趋势预测模型
│   └── shipping_mode_encoder.pkl     # 运输模式文本特征的 LabelEncoder 编码器
├── train_model.py                    # [MLOps] 离线数据清洗与模型训练脚本
├── api.py                            # [Service] FastAPI 在线实时推理服务接口
├── Dockerfile                        # Docker 镜像构建配置文件（多芯片架构适配）
└── docker-compose.yml                # Docker 容器多服务编排文件

部署与运行
1. 离线真数模型训练
确保已将 Kaggle 下载的 DataCoSupplyChainDataset.csv 放入 data/ 目录，然后在本地环境运行：py -3.11 train_model.py
运行完成后，model/ 目录下会生成最新的 4 个核心 .pkl 脑细胞文件。

2. 微服务容器化打包与运行（Docker）
由于项目采用了跨芯片架构适配与极速缓存清理机制，请依次执行以下命令：
# 1. 强制无缓存构建 Docker 胶囊镜像（解决跨芯片架构与顽固旧缓存问题）
docker compose build --no-cache

# 2. 启动微服务（解决 Windows 端口被系统锁死的 winnat 冲突，对外映射至安全端口 8081）
docker compose up -d

3. 接口联调与验收测试
微服务成功运行后，会自动生成 Swagger UI 交互式白皮书测试台。

验收网址：http://localhost:8081/docs

联调测试步骤：

打开上述网页，展开 POST /predict/risk 接口。

点击右上角 "Try it out" 激活编辑模式。

修改请求体（Request body）中的业务参数（例如故意制造亏损订单：将利润率改为负数）。

点击蓝色的 "Execute" 按钮，在下方 Response 中即可实时查看到带有 xai_analysis 的供应链智能风控 JSON 报文。

微服务内部通信：在最终的大系统联合编排中，后端主服务（backend-api）无需使用 localhost，可以直接在 Docker 虚拟局域网内通过虚拟域名直接通信：http://ai-service:8000/predict/risk。