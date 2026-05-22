// mock-server.js
import { WebSocketServer } from 'ws'

const wss = new WebSocketServer({ port: 8081 })

console.log('Mock WebSocket Server 已启动: ws://localhost:8081')

wss.on('connection', (ws) => {
  console.log('前端已连接')

  const sendStats = () => {
    const data = {
      type: 'stats',
      data: {
        totalOrders: Math.floor(Math.random() * 1000) + 12000,
        gmv: Math.floor(Math.random() * 100000) + 2300000,
        otdRate: parseFloat((Math.random() * 2 + 94).toFixed(1)),
        riskCount: Math.floor(Math.random() * 10),
        delayRate: parseFloat((Math.random() * 5 + 10).toFixed(1)),
        

        heatMap: [
          { name: '北京市', value: Math.floor(Math.random() * 1000) + 500 },
          { name: '上海市', value: Math.floor(Math.random() * 1000) + 500 },
          { name: '广东省', value: Math.floor(Math.random() * 1000) + 500 },
          { name: '浙江省', value: Math.floor(Math.random() * 1000) + 500 },
          { name: '江苏省', value: Math.floor(Math.random() * 1000) + 500 },
          { name: '四川省', value: Math.floor(Math.random() * 1000) + 500 }
        ]
      }
    }
    ws.send(JSON.stringify(data))
  }

  const sendAlert = () => {
    const alerts = [
      { orderId: 'ORD20260517001', riskType: '极高延迟交付风险', probability: 0.92, level: 'danger', icon: 'fas fa-exclamation-circle' },
      { orderId: 'ORD20260517002', riskType: '库存不足预警', probability: 0.88, level: 'warning', icon: 'fas fa-box-open' }
    ]
    const alert = alerts[Math.floor(Math.random() * alerts.length)]
    const data = {
      type: 'alert',
      data: {
        id: Date.now(),
        ...alert,
        timestamp: new Date().toISOString()
      }
    }
    ws.send(JSON.stringify(data))
  }

  sendStats()
  sendAlert()
  setInterval(sendStats, 3000)
  setInterval(sendAlert, 5000)
})