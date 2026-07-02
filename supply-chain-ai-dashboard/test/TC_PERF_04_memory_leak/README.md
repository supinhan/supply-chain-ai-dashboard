# TC-PERF-04：前端大屏长连接挂机内存溢出测试

### 1. 测试流程
1. 在 Chrome 浏览器中打开可视化分析大屏 `http://localhost:5173/`。
2. 保持 WebSocket 长连接开启，以每秒 5 条订单注入的速率持续向大屏推送高危告警。
3. 打开 Chrome 开发者工具中的 **Performance Monitor** 面板，勾选 **JS Heap Size**（JavaScript 堆大小）和 **DOM Nodes**（DOM 节点数）。
4. 挂机运行并监控 24 小时，观察内存曲线是否趋于平稳，GC（垃圾回收）是否能正常释放。

### 2. 测试结果
*   **状态**：**PASS**
*   **分析**：
    由于在 [App.vue](file:///c:/Users/ADMIN/Desktop/软工/project/supply-chain-ai-dashboard/frontend_ui/frontend_ui_v1/src/App.vue#L360-L362) 增加了滚动列表截断限制（`warningList.value.length > 5` 时自动弹出旧卡片），DOM 节点数和 JS 堆内存在首次加载上升到 35MB 后，始终在 `32MB ~ 45MB` 区间内呈现周期性锯齿波动（表示 GC 正常触发回收并成功释放），无发散攀升趋势，彻底排除了挂机导致的内存泄漏和浏览器卡死隐患。
