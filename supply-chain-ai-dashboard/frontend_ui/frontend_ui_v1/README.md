前端项目说明：AI 赋能企业供应链可视化分析系统
项目简介
本项目为 AI 赋能企业供应链可视化分析系统​ 的前端大屏部分，基于 Vue 3 + Vite + ECharts 开发。系统通过 WebSocket 实时接收后端推送的供应链数据，动态展示全局 KPI、物流热力图、风险预警和历史趋势，实现对企业供应链状态的实时监控与智能预警。
技术栈
核心框架：Vue 3 (Composition API)
构建工具：Vite
可视化图表：ECharts 5.x
实时通信：WebSocket (原生)
HTTP 客户端：Fetch API
样式方案：CSS3 (Glassmorphism 玻璃拟态)
环境要求
Node.js：>= 18.0.0
npm：>= 9.0.0
浏览器：Chrome 90+ / Edge 90+ (推荐)
测试调试：
使用mock-server.js模拟后端输入来调试输出结果
在新建终端cmd下
npm run dev
在另一终端cmd下
node mock-server.js
打开http://localhost:5173/观察效果
与后端交互说明
前端通过两种方式与后端通信，完全符合 PRD/SDD 文档规范。
1. WebSocket 实时数据 (UC-04, UC-06)
连接地址：ws://localhost:8000/api/v1/ws/alerts
用途：接收实时 KPI 更新和风险告警。
数据格式：
json
// 全局 KPI 更新
{
  "type": "stats",
  "data": {
    "total_orders": 12580,
    "total_gmv": 2345678,
    "risk_intercept_count": 5,
    "on_time_delivery_rate": 98.5,
    "delay_rate": 12.8,
    "heatMap": [{ "name": "北京市", "value": 820 }]
  }
}
// 风险告警推送
{
  "type": "alert",
  "data": {
    "id": 1700000000000,
    "order_id": "ORD20260517001",
    "risk_type": "极高延迟交付风险",
    "probability": 0.92,
    "level": "danger",
    "icon": "fas fa-exclamation-circle",
    "timestamp": "2026-05-17T10:30:00Z"
  }
}
2. HTTP 历史数据 (UC-07)
请求地址：GET http://localhost:8000/api/v1/kpi/history?hours=24
用途：获取历史进出货量趋势数据。
响应格式：
json
{
  "labels": ["5-10", "5-11", "5-12"],
  "inbound": [800, 900, 850],
  "outbound": [1200, 1100, 1300]
}
项目结构
纯文本
src/
├── App.vue          # 主组件，包含所有大屏视图和逻辑
├── main.js          # 应用入口
└── assets/          # 静态资源（图片、字体等）
配置说明
修改后端地址
如需连接不同的后端环境，请修改 src/App.vue中的连接地址：
javascript
// src/App.vue
const connectWebSocket = () => {
  // 修改为你的后端 WebSocket 地址
  socket = new WebSocket('ws://your-backend-domain:8000/api/v1/ws/alerts')
}
修改 HTTP 接口地址
如需修改历史数据的 HTTP 接口地址，请修改 src/App.vue中的 fetch 请求：
javascript
// src/App.vue
fetch('http://your-backend-domain:8000/api/v1/kpi/history')
  .then(res => res.json())
  .then(data => { /* ... */ })