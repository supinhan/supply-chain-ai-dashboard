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
        <h3><i class="fas fa-map-marked-alt"></i> 全球物流热力图</h3>
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
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

// ================== 数据定义 ==================
const stats = ref({
  totalOrders: 0,
  gmv: 0,
  otdRate: 0,
  riskCount: 0,
  delayRate: 0,
  orderStatus: [
    { value: 0, name: '已完成', itemStyle: { color: '#91cc75' } },
    { value: 0, name: '运输中', itemStyle: { color: '#5470c6' } },
    { value: 0, name: '待发货', itemStyle: { color: '#fac858' } }
  ]
})

const warningList = ref([])
let socket = null
let mapChart = null
let pieChart = null
let historyChart = null
let forecastChart = null

// WebSocket 状态显示
const wsStatus = ref('connecting')
const wsText = ref('连接中...')
const wsIcon = ref('fa-spinner fa-spin')

// ================== 城市 → 国家 映射表（关键） ==================
const cityToCountry = {
  // 美国城市（后端返回的主要城市）
  'caguas': 'United States of America',
  'dallas': 'United States of America',
  'mount prospect': 'United States of America',
  'mt. prospect': 'United States of America',
  'wilkes barre': 'United States of America',
  'wheaton': 'United States of America',
  'tonawanda': 'United States of America',
  'san ramon': 'United States of America',
  'san jose': 'United States of America',
  'salinas': 'United States of America',
  'roseville': 'United States of America',
  'rochester': 'United States of America',
  'rancho cordova': 'United States of America',
  'peabody': 'United States of America',
  'paramount': 'United States of America',
  'panorama city': 'United States of America',
  'newark': 'United States of America',
  'atlanta': 'United States of America',
  'miami': 'United States of America',
  'los angeles': 'United States of America',
  'long beach': 'United States of America',
  // 其他国家城市（备用）
  'beijing': 'China',
  'shanghai': 'China',
  'guangzhou': 'China',
  'tokyo': 'Japan',
  'london': 'United Kingdom',
  'paris': 'France',
  'berlin': 'Germany',
  'sydney': 'Australia',
  'toronto': 'Canada',
  'mexico city': 'Mexico',
  'moscow': 'Russia',
  'seoul': 'South Korea',
  'singapore': 'Singapore',
  'bangkok': 'Thailand',
  'dubai': 'United Arab Emirates',
  'sao paulo': 'Brazil',
  'buenos aires': 'Argentina',
  'johannesburg': 'South Africa',
  'cairo': 'Egypt',
  'delhi': 'India',
  'mumbai': 'India'
}

// ================== WebSocket 连接 ==================
const connectWebSocket = () => {
  socket = new WebSocket('ws://localhost:8000/api/v1/ws/alerts')

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
      // ========== 城市热度 → 国家热度（核心逻辑） ==========
      const rawHeatMap = Array.isArray(res.data.heatMap) ? res.data.heatMap : []
      const countryAcc = {}
      
      rawHeatMap.forEach(item => {
        const cityKey = String(item.name || '').trim().toLowerCase()
        const country = cityToCountry[cityKey] || 'Unknown'
        if (country !== 'Unknown') {
          countryAcc[country] = (countryAcc[country] || 0) + Math.max(Number(item.value) || 0, 0)
        }
      })

      const fixedHeatMap = Object.keys(countryAcc)
        .map(name => ({ name, value: countryAcc[name] }))

      // 更新 KPI
      stats.value = {
        totalOrders: res.data.totalOrders || 0,
        gmv: res.data.gmv || 0,
        otdRate: res.data.otdRate || 0,
        riskCount: res.data.riskCount || 0,
        delayRate: res.data.delayRate || 0,
        orderStatus: res.data.orderStatus || stats.value.orderStatus
      }
      
      // 更新热力图
      if (fixedHeatMap.length > 0 && mapChart) {
        console.log('✅ 热力图（归到国家）:', fixedHeatMap)
        mapChart.setOption({
          series: [{
            data: fixedHeatMap
          }]
        })
      }
    } else if (res.type === 'alert') {
      console.log('收到预警:', res.data)
      warningList.value.unshift({
        id: res.data.id,
        orderId: res.data.orderId,
        riskType: res.data.riskType,
        probability: res.data.probability,
        level: res.data.level || 'danger',
        icon: res.data.icon || 'fas fa-exclamation-circle',
        timestamp: res.data.timestamp
      })
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

// ================== 加载历史数据 ==================
const loadHistoryData = async () => {
  try {
    console.log('📈 加载历史数据...')
    const response = await fetch('http://localhost:8000/api/v1/kpi/history?hours=24')
    const data = await response.json()
    
    console.log('📈 历史数据:', data)
    
    const buckets = data.items.map(item => item.bucket)
    const orderCounts = data.items.map(item => item.order_count)
    const riskCounts = data.items.map(item => item.risk_count)
    
    if (historyChart) {
      historyChart.setOption({
        xAxis: {
          type: 'category',
          data: buckets
        },
        series: [
          {
            name: '出货量',
            type: 'line',
            smooth: true,
            data: orderCounts
          },
          {
            name: '进货量',
            type: 'line',
            smooth: true,
            data: riskCounts
          }
        ]
      })
    }
  } catch (error) {
    console.error('❌ 历史数据加载失败:', error)
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
  pieChart = echarts.init(document.getElementById('pie-chart'))
  
  const updatePieChart = () => {
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['50%', '70%'],
        label: {
          show: true,
          position: 'center',
          formatter: () => stats.value.totalOrders.toString(),
          color: '#fff',
          fontSize: 16
        },
        data: stats.value.orderStatus,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#0d1117',
          borderWidth: 2
        }
      }]
    })
  }
  
  updatePieChart()

  // 监听数据变化，自动更新饼图
  watch(() => stats.value.orderStatus, () => {
    updatePieChart()
  }, { deep: true })

  // 2. 全球物流热力地图（美国发货 → 全球收货）
  mapChart = echarts.init(document.getElementById('map-chart'))

  fetch('/world.json')
    .then(res => {
      if (!res.ok) throw new Error('world.json 加载失败，请确认文件在 public/ 目录下')
      return res.json()
    })
    .then(geo => {
      echarts.registerMap('world', geo)
      mapChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: p => `${p.name}<br/>发货热度: ${p.value ?? 0}` },
        visualMap: {
          min: 0,
          max: 5000,
          left: 'left',
          bottom: 10,
          text: ['高', '低'],
          textStyle: { color: '#ccc' },
          calculable: true,
          inRange: {
            color: ['#ffffff', '#ffe6e6', '#ffb3b3', '#ff6666', '#cc0000']
          }
        },
        geo: {
          map: 'world',
          roam: true,
          zoom: 1.1,
          center: [-98, 38],
          silent: false,
          itemStyle: {
            areaColor: '#ffffff',
            borderColor: '#cccccc',
            borderWidth: 0.5
          },
          emphasis: {
            itemStyle: {
              areaColor: '#ffcccc',
              shadowBlur: 10,
              shadowColor: 'rgba(255,0,0,0.3)'
            },
            label: { show: true, color: '#990000', fontSize: 11 }
          },
          regions: [{
            name: 'United States of America',
            itemStyle: {
              areaColor: '#cc0000',
              shadowBlur: 15,
              shadowColor: 'rgba(255,0,0,0.5)',
              borderColor: '#ff3333',
              borderWidth: 1.2
            },
            label: { show: true, color: '#ffffff', fontSize: 12, fontWeight: 'bold' }
          }]
        },
        series: [{
          name: '全球收货热度',
          type: 'map',
          map: 'world',
          geoIndex: 0,
          data: [],
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: '#ff0000' } }
        }]
      })
    })
    .catch(err => {
      console.error('🌍 世界地图加载失败:', err.message)
    })

  // 3. 历史趋势折线图
  historyChart = echarts.init(document.getElementById('history-chart'))
  historyChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#aaa' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: [],
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
        data: [],
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
        data: [],
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
  forecastChart = echarts.init(document.getElementById('forecast-chart'))
  forecastChart.setOption({
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

  // 加载历史数据
  loadHistoryData()

  // 窗口自适应
  window.addEventListener('resize', () => {
    pieChart?.resize()
    mapChart?.resize()
    historyChart?.resize()
    forecastChart?.resize()
  })
})

onUnmounted(() => {
  if (socket) socket.close()
  if (pieChart) pieChart.dispose()
  if (mapChart) mapChart.dispose()
  if (historyChart) historyChart.dispose()
  if (forecastChart) forecastChart.dispose()
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
  animation: blink 1s infinite;
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