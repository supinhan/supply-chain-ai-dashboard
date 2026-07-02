# TC-FUNC-05：WebSocket 实时广播与数据推送测试

### 1. 测试流程
1. 连接至 WebSocket 路由端口 `ws://127.0.0.1:8000/api/v1/ws/alerts`。
2. 监听连接成功后，服务端自动发出的第一帧 `stats` 指标推送。
3. 校验 `stats` 数据结构，以及键名是否符合 camelCase（例如 `totalOrders`, `gmv`, `riskCount`）。
4. 运行 `test_websocket.py` 脚本：
   ```bash
   python test/TC_FUNC_05_ws_broadcast/test_websocket.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-FUNC-05 (WebSocket 实时广播与数据推送测试) ===
    正在建立连接到 ws://127.0.0.1:8000/api/v1/ws/alerts ...
    WebSocket 握手成功！等待接收第一帧消息...
    收到帧消息类型: stats
    -> [PASS] 成功接收 stats 数据，当前订单总数: 73, GMV: 17162.35
    ```
