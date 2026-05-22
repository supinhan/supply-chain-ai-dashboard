<template>
  <div class="app-container">
    <!-- 顶部标题 -->
    <header class="header">
      <h1><i class="fas fa-brain"></i> AI 赋能企业供应链可视化分析系统</h1>
      <div class="status" :class="wsStatus">
        <i class="fas" :class="wsIcon"></i> {{ wsText }}
      </div>
    </header>

    <!-- 全局 KPI 指标盘 -->
    <div class="metrics-grid">
      <div class="metric-card glass">
        <div class="metric-icon"><i class="fas fa-shopping-cart"></i></div>
        <div class="metric-info">
          <p class="metric-label">累计订单量</p>
          <p class="metric-value">{{ stats.totalOrders }}</p>
        </div>
      </div>

      <div class="metric-card glass">
        <div class="metric-icon"><i class="fas fa-yen-sign"></i></div>
        <div class="metric-info">
          <p class="metric-label">实时 GMV</p>
          <p class="metric-value">¥ {{ typeof stats.gmv === 'number' ? stats.gmv.toLocaleString() : '0' }}</p>
        </div>
      </div>

      <div class="metric-card glass success">
        <div class="metric-icon"><i class="fas fa-check-circle"></i></div>
        <div class="metric-info">
          <p class="metric-label">准交率 (OTD)</p>
          <p class="metric-value">{{ typeof stats.otdRate === 'number' ? stats.otdRate.toFixed(1) : '0' }}%</p>
        </div>
      </div>

      <div class="metric-card glass danger">
        <div class="metric-icon"><i class="fas fa-robot"></i></div>
        <div class="metric-info">
          <p class="metric-label">风险拦截次数</p>
          <p class="metric-value">{{ stats.riskCount }}</p>
          <p class="metric-desc">AI 预测拖延率 {{ typeof stats.delayRate === 'number' ? stats.delayRate.toFixed(1) : '0' }}%</p>
        </div>
      </div>
    </div>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 左侧：订单状态 -->
      <section class="chart-card glass">
        <h3><i class="fas fa-chart-pie"></i> 订单实时状态</h3>
        <div id="pie-chart" class="chart-box"></div>
      </section>

      <!-- 中间：地图 + 历史趋势 + 预测 -->
      <section class="chart-card glass middle">
        <h3><i class="fas fa-map-marked-alt"></i> 全国物流热力图</h3>
        <div id="map-chart" class="chart-box"></div>

        <div class="sub-charts">
          <!-- 历史趋势折线图 -->
          <div class="sub-chart">
            <h4><i class="fas fa-history"></i> 历史趋势（近7天）</h4>
            <div id="history-chart" class="chart-box small"></div>
          </div>

          <!-- 未来成交预测 -->
          <div class="sub-chart">
            <h4><i class="fas fa-chart-line"></i> 未来7天成交预测</h4>
            <div id="forecast-chart" class="chart-box small"></div>
          </div>
        </div>
      </section>

      <!-- 右侧：实时预警滚动播报 -->
      <section class="chart-card glass">
        <h3><i class="fas fa-exclamation-triangle"></i> 风险事件追踪</h3>
        <div class="alert-list">
          <div
            v-for="item in warningList"
            :key="item.id"
            class="alert-item"
            :class="item.level"
          >
            <div class="alert-icon">
              <i :class="item.icon"></i>
            </div>
            <div class="alert-content">
              <div class="alert-title">
                {{ item.riskType || '未知风险' }}
                <span class="alert-probability" v-if="item.probability !== undefined">
                  风险概率: {{ (item.probability * 100).toFixed(0) }}%
                </span>
              </div>
              <div class="alert-desc">
                订单号: {{ item.orderId || '未知订单' }}
              </div>
              <div class="alert-time">{{ formatTime(item.timestamp) }}</div>
            </div>
          </div>
          <div v-if="warningList.length === 0" class="no-alert">
            <i class="fas fa-check-circle"></i> 系统运行平稳
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

// ================== 数据定义 ==================
const stats = ref({
  totalOrders: 0,
  gmv: 0,          //  初始化为数字 0
  otdRate: 0,      //  初始化为数字 0
  riskCount: 0,
  delayRate: 0
})

const warningList = ref([])
let socket = null
let mapChart = null

// WebSocket 状态显示
const wsStatus = ref('connecting')
const wsText = ref('连接中...')
const wsIcon = ref('fa-spinner fa-spin')

// ================== WebSocket 连接 ==================
const connectWebSocket = () => {
  socket = new WebSocket('ws://localhost:8081')

  socket.onopen = () => {
    wsStatus.value = 'connected'
    wsText.value = '实时同步中'
    wsIcon.value = 'fa-circle'
    console.log('WebSocket 连接成功')
  }

  socket.onmessage = (event) => {
    const res = JSON.parse(event.data)
    console.log('收到数据:', res)
    
    if (res.type === 'stats') {
      stats.value = res.data
      console.log('更新 KPI:', stats.value)
      
      // 更新热力图
      if (res.data.heatMap && mapChart) {
        console.log('更新热力图')
        mapChart.setOption({
          series: [{
            data: res.data.heatMap
          }]
        })
      }
    } else if (res.type === 'alert') {
      console.log('收到预警:', res.data)
      warningList.value.unshift(res.data)
      if (warningList.value.length > 5) {
        warningList.value.pop()
      }
    }
  }

  socket.onerror = (error) => {
    console.error('WebSocket 错误:', error)
    wsStatus.value = 'error'
    wsText.value = '连接失败'
    wsIcon.value = 'fa-times-circle'
  }

  socket.onclose = () => {
    console.log('🔌 WebSocket 连接关闭')
    wsStatus.value = 'error'
    wsText.value = '连接断开'
    wsIcon.value = 'fa-times-circle'
  }
}

// ================== 时间格式化 ==================
const formatTime = (iso) => {
  const d = new Date(iso)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

// ================== ECharts 初始化 ==================
onMounted(() => {
  connectWebSocket()

  // 1. 订单状态饼图
  const pie = echarts.init(document.getElementById('pie-chart'))
  pie.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['50%', '70%'],
      label: { show: true, position: 'center', formatter: '{c}', color: '#fff', fontSize: 16 },
      data: [
        { value: 735, name: '已完成', itemStyle: { color: '#91cc75' } },
        { value: 310, name: '运输中', itemStyle: { color: '#5470c6' } },
        { value: 234, name: '待发货', itemStyle: { color: '#fac858' } }
      ]
    }]
  })

  // 2. 物流热力地图
  mapChart = echarts.init(document.getElementById('map-chart'))
  fetch('https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json')
    .then(res => res.json())
    .then(geo => {
      echarts.registerMap('china', geo)
      mapChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}<br/>热度: {c}' },
        visualMap: {
          min: 0,
          max: 1000,
          left: 'left',
          top: 'bottom',
          text: ['高', '低'],
          calculable: true,
          inRange: {
            color: ['#1e90ff', '#fff', '#ff4500']
          }
        },
        series: [{
          name: '全国物流',
          type: 'map',
          map: 'china',
          roam: true,
          zoom: 1.2,
          label: { show: false },
          emphasis: { label: { show: true, color: '#fff' } },
          data: []   // 初始为空，等待WebSocket推送
        }]
      })
    })

  // 3. 历史趋势折线图
  const history = echarts.init(document.getElementById('history-chart'))
  history.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#aaa' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['5-10', '5-11', '5-12', '5-13', '5-14', '5-15', '5-16'],
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#aaa' }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#555' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      axisLabel: { color: '#aaa' }
    },
    series: [
      {
        name: '出货量',
        type: 'line',
        smooth: true,
        data: [1200, 1100, 1300, 1250, 1400, 1350, 1500],
        lineStyle: { color: '#91cc75', width: 3 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(145, 204, 117, 0.5)' },
            { offset: 1, color: 'rgba(145, 204, 117, 0.1)' }
          ])
        }
      },
      {
        name: '进货量',
        type: 'line',
        smooth: true,
        data: [800, 900, 850, 950, 1000, 1100, 1050],
        lineStyle: { color: '#5470c6', width: 3 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(84, 112, 198, 0.5)' },
            { offset: 1, color: 'rgba(84, 112, 198, 0.1)' }
          ])
        }
      }
    ]
  })

  // 4. 未来成交预测
  const forecast = echarts.init(document.getElementById('forecast-chart'))
  forecast.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['D+1', 'D+2', 'D+3', 'D+4', 'D+5', 'D+6', 'D+7'],
      axisLine: { lineStyle: { color: '#555' } },
      axisLabel: { color: '#aaa' }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#555' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      axisLabel: { color: '#aaa' }
    },
    series: [{
      name: '预测成交量',
      type: 'line',
      smooth: true,
      data: [820, 932, 901, 1234, 1290, 1330, 1520],
      lineStyle: { color: '#fac858', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(250, 200, 88, 0.5)' },
          { offset: 1, color: 'rgba(250, 200, 88, 0.1)' }
        ])
      }
    }]
  })

  // 窗口自适应
  window.addEventListener('resize', () => {
    pie.resize()
    mapChart.resize()
    history.resize()
    forecast.resize()
  })
})

onUnmounted(() => {
  if (socket) socket.close()
})
</script>

<style scoped>
/* ================== 全局样式 ================== */
.app-container {
  min-height: 100vh;
  background: radial-gradient(circle at center, #1a233a 0%, #0d1117 100%);
  color: #e0e0e0;
  font-family: 'Microsoft YaHei', sans-serif;
  padding: 20px;
  box-sizing: border-box;
}

/* ================== 头部 ================== */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.header h1 {
  margin: 0;
  font-size: 24px;
  background: linear-gradient(90deg, #fff, #4facfe);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.status {
  font-size: 12px;
  padding: 5px 10px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.1);
}
.status.connected { color: #91cc75; }
.status.connecting { color: #fac858; }
.status.error { color: #ee6666; }

/* ================== KPI 指标盘 ================== */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}
.metric-card {
  padding: 20px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 15px;
}
.metric-card.glass {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
}
.metric-card.success { border-color: rgba(145, 204, 117, 0.3); }
.metric-card.danger { border-color: rgba(255, 71, 87, 0.3); }

.metric-icon {
  width: 50px;
  height: 50px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}
.metric-card.glass .metric-icon { background: rgba(79, 172, 254, 0.2); color: #4facfe; }
.metric-card.success .metric-icon { background: rgba(145, 204, 117, 0.2); color: #91cc75; }
.metric-card.danger .metric-icon { background: rgba(255, 71, 87, 0.2); color: #ff4757; }

.metric-info { flex: 1; }
.metric-label { margin: 0 0 5px; font-size: 14px; color: #aaa; }
.metric-value { margin: 0; font-size: 24px; font-weight: bold; color: #fff; }
.metric-desc { margin: 5px 0 0; font-size: 12px; color: #ff6b6b; }

/* ================== 主内容区 ================== */
.main-content {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  gap: 20px;
  height: calc(100vh - 200px);
}
.chart-card {
  padding: 20px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chart-card.glass {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
}
.chart-card h3 {
  margin: 0 0 15px;
  font-size: 16px;
  color: #fff;
  border-left: 4px solid #4facfe;
  padding-left: 10px;
}
.chart-box {
  flex: 1;
  width: 100%;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

/* 中间子图表 */
.middle { gap: 15px; }
.sub-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  margin-top: 15px;
}
.sub-chart h4 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #ccc;
}
.small { height: 180px; }

/* ================== 预警列表 ================== */
.alert-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 5px;
}
.alert-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  margin-bottom: 10px;
  border-radius: 6px;
  border-left: 3px solid transparent;
  background: rgba(255, 255, 255, 0.03);
  animation: blink 1s infinite; /* 高风险闪烁 */
}
.alert-item.danger { border-left-color: #ff4757; }
.alert-item.warning { border-left-color: #ffa502; }

.alert-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.alert-item.danger .alert-icon { background: rgba(255, 71, 87, 0.2); color: #ff4757; }
.alert-item.warning .alert-icon { background: rgba(255, 165, 2, 0.2); color: #ffa502; }

.alert-content { flex: 1; }
.alert-title {
  font-size: 13px;
  font-weight: bold;
  color: #fff;
  display: flex;
  justify-content: space-between;
}
.alert-probability {
  font-size: 11px;
  color: #ff6b6b;
}
.alert-desc {
  font-size: 12px;
  color: #bbb;
  margin-top: 4px;
}
.alert-time {
  font-size: 11px;
  color: #888;
  margin-top: 4px;
}
.no-alert {
  text-align: center;
  padding: 40px 0;
  color: #555;
}

/* 动画 */
@keyframes blink {
  0%, 100% { box-shadow: 0 0 10px rgba(255, 71, 87, 0.7); }
  50% { box-shadow: 0 0 20px rgba(255, 71, 87, 1); }
}

/* 滚动条 */
.alert-list::-webkit-scrollbar { width: 5px; }
.alert-list::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); }
.alert-list::-webkit-scrollbar-thumb { background: rgba(0,150,255,0.5); border-radius: 3px; }
</style>