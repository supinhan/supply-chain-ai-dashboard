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
        <h3><i class="fas fa-map-marked-alt"></i> 物流热力图</h3>
        <div id="map-chart" class="chart-box"></div>

        <div class="sub-charts">
          <div class="sub-chart">
            <h4><i class="fas fa-history"></i> 历史趋势（近24小时）</h4>
            <div id="history-chart" class="chart-box small"></div>
          </div>

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

              <!-- ✅ 安全显示 xai_analysis -->
              <div v-if="item.xaiAnalysis && Object.keys(item.xaiAnalysis).length > 0" class="xai-box">
                <p class="xai-title">AI 决策依据</p>
                <div
                  v-for="(score, feature) in item.xaiAnalysis"
                  :key="feature"
                  class="xai-item"
                >
                  <span class="xai-feature">{{ feature }}</span>
                  <div class="xai-bar">
                    <div
                      class="xai-fill"
                      :style="{ width: parseFloat(score) * 100 + '%' }"
                    ></div>
                  </div>
                  <span class="xai-score">{{ (parseFloat(score) * 100).toFixed(1) }}%</span>
                </div>
              </div>
              <div v-else class="xai-box no-data">
                <p class="xai-title">AI 决策依据</p>
                <p class="xai-no-data">暂无分析数据</p>
              </div>
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
// ✅ 导入映射表
import { cityToRegion, usStates } from './utils/cityRegionMapping.js'

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
let reconnectTimer = null
let reconnectAttempts = 0
let shouldReconnect = true
let pendingStatsData = null
const registeredMaps = new Set()

// WebSocket 状态显示
const wsStatus = ref('connecting')
const wsText = ref('连接中...')
const wsIcon = ref('fa-spinner fa-spin')

// ================== KPI 与地图渲染 ==================
const buildMapPayload = (data) => {
  const rawHeatMap = Array.isArray(data?.heatMap) ? data.heatMap : []
  const backendRegionHeatMap = Array.isArray(data?.regionHeatMap) ? data.regionHeatMap : []
  const usData = []
  const worldData = []

  let mapType = data?.heatMapMeta?.mapType || 'NA_STATES'
  let mapData = backendRegionHeatMap

  if (mapData.length === 0) {
    rawHeatMap.forEach(item => {
      const cityKey = String(item.name || '').trim().toLowerCase()
      const region = cityToRegion[cityKey]

      if (!region) {
        console.warn('未找到对应区域:', item.name)
        return
      }

      const value = Math.max(Number(item.value) || 0, 0)
      if (usStates.has(region)) {
        usData.push({ name: region, value })
      } else {
        worldData.push({ name: region, value })
      }
    })

    mapType = 'NA_STATES'
    mapData = usData

    if (worldData.length > 0) {
      mapType = 'WORLD'
      const usTotal = usData.reduce((sum, item) => sum + item.value, 0)
      if (usTotal > 0) {
        worldData.push({ name: 'United States', value: usTotal })
      }
      mapData = worldData
    }
  }

  return { mapType, mapData }
}

const renderHeatMap = (data) => {
  pendingStatsData = data
  if (!mapChart) return

  const { mapType, mapData } = buildMapPayload(data)
  if (!registeredMaps.has(mapType)) {
    console.warn(`地图 ${mapType} 尚未注册，等待 GeoJSON 加载完成后渲染`)
    return
  }

  if (mapData.length === 0) {
    mapChart.clear()
    return
  }

  const values = mapData.map(d => d.value)
  const maxValue = Math.max(...values, 1)
  const scaledData = mapData.map(item => ({
    name: item.name,
    value: Math.sqrt(Math.max(Number(item.value) || 0, 0))
  }))
  const scaledMax = Math.sqrt(maxValue)

  let center = [-100, 40]
  let zoom = 1.5

  if (mapType === 'WORLD') {
    center = [0, 20]
    zoom = 1.2
  }

  mapChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: p => `${p.name}<br/>热度: ${p.value ? (p.value * p.value).toFixed(0) : 0}`
    },
    visualMap: {
      min: 0,
      max: scaledMax,
      left: 'left',
      bottom: 10,
      text: ['高', '低'],
      textStyle: { color: '#ccc' },
      calculable: true,
      inRange: {
        color: [
          '#ffffff', '#ffcccc', '#ff9999', '#ff6666',
          '#ff3333', '#cc0000', '#990000', '#660000'
        ]
      },
      outOfRange: { color: '#ffffff' }
    },
    geo: {
      map: mapType,
      roam: true,
      zoom: zoom,
      center: center,
      itemStyle: {
        areaColor: '#ffffff',
        borderColor: '#cccccc',
        borderWidth: 0.5
      },
      emphasis: {
        itemStyle: {
          areaColor: '#f0f0f0',
          shadowColor: 'rgba(255, 100, 100, 0.5)',
          shadowBlur: 10
        }
      }
    },
    series: [{
      name: '物流热度',
      type: 'map',
      map: mapType,
      geoIndex: 0,
      data: scaledData,
      emphasis: {
        itemStyle: {
          shadowBlur: 20,
          shadowColor: 'rgba(255, 50, 50, 0.8)',
          borderColor: '#ff3333',
          borderWidth: 2,
        },
        label: {
          show: true,
          color: '#fff',
          fontSize: 12,
          fontWeight: 'bold'
        }
      }
    }]
  })
}

const applyStatsData = (data) => {
  if (!data) return
  renderHeatMap(data)
  stats.value = {
    totalOrders: data.totalOrders || 0,
    gmv: data.gmv || 0,
    otdRate: data.otdRate || 0,
    riskCount: data.riskCount || 0,
    delayRate: data.delayRate || 0,
    orderStatus: data.orderStatus || stats.value.orderStatus
  }
}

const loadRealtimeKpi = async () => {
  try {
    const res = await fetch('/api/v1/kpi/realtime')
    if (!res.ok) throw new Error(`KPI 请求失败: ${res.status}`)
    const data = await res.json()
    applyStatsData(data)
  } catch (err) {
    console.error('实时 KPI 加载失败:', err)
  }
}

const loadRecentAlerts = async () => {
  try {
    const res = await fetch('/api/v1/alerts/recent?limit=5')
    if (!res.ok) throw new Error(`最近告警请求失败: ${res.status}`)
    const data = await res.json()
    warningList.value = (Array.isArray(data.items) ? data.items : []).map(item => ({
      id: item.id,
      orderId: item.order_id,
      riskType: item.risk_type,
      probability: item.probability,
      level: 'danger',
      icon: 'fas fa-exclamation-circle',
      timestamp: item.timestamp,
      xaiAnalysis: item.xai_analysis || {}
    }))
  } catch (err) {
    console.error('最近告警加载失败:', err)
  }
}

const addAlertItem = (data) => {
  if (!data) return
  const alertId = data.id
  if (alertId !== undefined && warningList.value.some(item => item.id === alertId)) return

  warningList.value.unshift({
    id: alertId,
    orderId: data.orderId,
    riskType: data.riskType,
    probability: data.probability,
    level: data.level || 'danger',
    icon: data.icon || 'fas fa-exclamation-circle',
    timestamp: data.timestamp,
    xaiAnalysis: data.xai_analysis || {}
  })
  if (warningList.value.length > 5) {
    warningList.value.pop()
  }
}

const scheduleReconnect = () => {
  if (!shouldReconnect) return
  if (reconnectTimer) window.clearTimeout(reconnectTimer)

  reconnectAttempts += 1
  const delay = Math.min(30000, 1000 * (2 ** Math.min(reconnectAttempts - 1, 5)))
  wsStatus.value = 'connecting'
  wsText.value = `${Math.ceil(delay / 1000)}秒后重连`
  wsIcon.value = 'fa-spinner fa-spin'
  reconnectTimer = window.setTimeout(() => {
    connectWebSocket()
  }, delay)
}

// ================== WebSocket 连接 ==================
const connectWebSocket = () => {
  if (socket && socket.readyState === WebSocket.OPEN) return

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  socket = new WebSocket(`${protocol}//${host}/api/v1/ws/alerts`)

  socket.onopen = () => {
    wsStatus.value = 'connected'
    wsText.value = '实时同步中'
    wsIcon.value = 'fa-circle'
    reconnectAttempts = 0
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    console.log('WebSocket 连接成功')
  }

  socket.onmessage = (event) => {
    const res = JSON.parse(event.data)
    console.log('收到数据:', res)
    
    if (res.type === 'stats') {
      applyStatsData(res.data)
    } else if (res.type === 'alert') {
      console.log('收到预警:', res.data)
      addAlertItem(res.data)
    }
  }

  socket.onerror = (error) => {
    console.error('WebSocket 错误:', error)
    wsStatus.value = 'error'
    wsText.value = '连接失败'
    wsIcon.value = 'fa-times-circle'
  }

  socket.onclose = () => {
    console.log('WebSocket 连接关闭')
    socket = null
    if (!shouldReconnect) return
    wsStatus.value = 'error'
    wsText.value = '连接断开'
    wsIcon.value = 'fa-times-circle'
    scheduleReconnect()
  }
}

// ================== 加载历史数据 ==================
const loadHistoryData = async () => {
  try {
    console.log('📈 加载历史趋势...')
    const res = await fetch('/api/v1/kpi/history?hours=24')
    if (!res.ok) throw new Error(`历史趋势请求失败: ${res.status}`)
    const data = await res.json()

    console.log('📈 历史数据:', data)

    const buckets = data.items.map(item => {
      const d = new Date(item.bucket)
      return `${d.getMonth() + 1}-${d.getDate()} ${d.getHours()}:00`
    })

    const orderCounts = data.items.map(item => item.order_count)
    const riskCounts = data.items.map(item => item.risk_count)

    if (historyChart) {
      historyChart.setOption({
        xAxis: { type: 'category', data: buckets },
        series: [
          { name: '出货量', type: 'line', smooth: true, data: orderCounts },
          { name: '进货量', type: 'line', smooth: true, data: riskCounts }
        ]
      })
      console.log('✅ 历史趋势渲染完成')
    }
  } catch (err) {
    console.error('❌ 历史趋势加载失败:', err)
  }
}

const renderForecastChart = (days, values) => {
  if (!forecastChart) return

  forecastChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: days,
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
      data: values,
      lineStyle: { color: '#fac858', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(250, 200, 88, 0.5)' },
          { offset: 1, color: 'rgba(250, 200, 88, 0.1)' }
        ])
      }
    }]
  })
}

// ================== 加载未来7天预测数据 ==================
const loadForecastData = async () => {
  try {
    console.log('📈 加载未来7天预测...')
    const res = await fetch('/api/v1/forecast')
    if (!res.ok) throw new Error(`预测请求失败: ${res.status}`)
    const data = await res.json()

    console.log('📈 预测数据:', data)

    renderForecastChart(
      data.days || ['D+1', 'D+2', 'D+3', 'D+4', 'D+5', 'D+6', 'D+7'],
      data.values || [820, 932, 901, 1234, 1290, 1330, 1520]
    )
  } catch (err) {
    console.error('❌ 未来7天预测加载失败，使用死数据兜底:', err)
    renderForecastChart(
      ['D+1', 'D+2', 'D+3', 'D+4', 'D+5', 'D+6', 'D+7'],
      [820, 932, 901, 1234, 1290, 1330, 1520]
    )
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

  watch(() => stats.value.orderStatus, () => {
    updatePieChart()
  }, { deep: true })

  // 2. 热力地图（支持自动切换）
  mapChart = echarts.init(document.getElementById('map-chart'))

  // 加载美国州地图
  fetch('/na-states.json')
    .then(res => {
      if (!res.ok) throw new Error('na-states.json 加载失败')
      return res.json()
    })
    .then(geo => {
      echarts.registerMap('NA_STATES', geo)
      registeredMaps.add('NA_STATES')
      console.log('✅ 北美州地图加载成功')
      if (pendingStatsData) renderHeatMap(pendingStatsData)
    })
    .catch(err => {
      console.error('🌍 北美地图加载失败:', err.message)
    })

  // 加载世界地图
  fetch('/world.json')
    .then(res => {
      if (!res.ok) throw new Error('world.json 加载失败')
      return res.json()
    })
    .then(geo => {
      echarts.registerMap('WORLD', geo)
      registeredMaps.add('WORLD')
      console.log('✅ 世界地图加载成功')
      if (pendingStatsData) renderHeatMap(pendingStatsData)
    })
    .catch(err => {
      console.error('🌍 世界地图加载失败:', err.message)
    })

  // 3. 历史趋势折线图
  setTimeout(() => {
    const el = document.getElementById('history-chart')
    if (!el) return

    historyChart = echarts.init(el)
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
    historyChart.resize()
    loadHistoryData()
  }, 300)

  // 4. 未来成交预测
  forecastChart = echarts.init(document.getElementById('forecast-chart'))
  loadForecastData()

  loadRealtimeKpi()
  loadRecentAlerts()
  loadHistoryData()

  window.addEventListener('resize', () => {
    pieChart?.resize()
    mapChart?.resize()
    historyChart?.resize()
    forecastChart?.resize()
  })
})

onUnmounted(() => {
  shouldReconnect = false
  if (reconnectTimer) window.clearTimeout(reconnectTimer)
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

/* XAI 展示样式 */
.xai-box {
  margin-top: 6px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  font-size: 12px;
}
.xai-title {
  color: #ff6b6b;
  margin-bottom: 4px;
  font-weight: bold;
}
.xai-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}
.xai-feature {
  color: #ccc;
  min-width: 80px;
}
.xai-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}
.xai-fill {
  height: 100%;
  background: linear-gradient(90deg, #ff4757, #ffa502);
  border-radius: 3px;
}
.xai-score {
  color: #aaa;
  min-width: 36px;
  text-align: right;
}

/* 无数据占位符 */
.xai-no-data {
  color: #888;
  font-size: 11px;
  text-align: center;
  padding: 8px 0;
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
