# TC-COMP-02：主流浏览器兼容性测试

### 1. 测试流程
1. 访问系统前端页面并使用四大主流内核浏览器进行测试：
   *   **Google Chrome (v125+)**：Blink 内核。
   *   **Mozilla Firefox (v126+)**：Gecko 内核。
   *   **Microsoft Edge (v124+)**：Blink 内核。
   *   **Apple Safari (v17+)**：WebKit 内核。
2. 重点对比 CSS 变量（CSS Custom Properties）、高阶滤镜（`backdrop-filter` 磨砂玻璃效果）、Flex/Grid 栅格系统的渲染差异，确保各浏览器表现完全一致。

### 2. 测试结果
*   **状态**：**PASS**
*   **结果明细**：
    *   **Chrome / Edge**：对 CSS 滤镜与动画特效支持最完美，长连接稳定无断流。
    *   **Firefox**：在 Firefox 下由于其特定的 CSS 滚动条规范，调整了滚动条隐藏样式以确保大屏“无滚轴滚动”。
    *   **Safari**：旧版本 Safari 对 `backdrop-filter` 的毛玻璃效果需要 `-webkit-backdrop-filter` 前缀，大屏 CSS 中已默认添加该前缀兼容，效果呈现饱满平滑。
