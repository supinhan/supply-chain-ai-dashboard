# TC-FUNC-07：AI 推理服务离线容灾测试

### 1. 测试流程
1. 在 AI 推理微服务在线时，请求销量预测，数据源 (`source`) 应为 `ai-service`。
2. 关闭 AI 服务进程（模拟容器挂起），再次发起请求。
3. 验证返回的数据源 (`source`) 切换为 `history-fallback`，输出成功降级到数据库的历史算术平均销量值。
4. 执行 `test_ai_fallback.py` 脚本：
   ```bash
   python test/TC_FUNC_07_ai_fallback/test_ai_fallback.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-FUNC-07 (AI 推理服务离线容灾测试) ===

    [步骤 1] 正常情况下请求未来销量预测接口 (AI 推理服务在线)...
    响应状态码: 200
    返回结果 (source): ai-service
    预测天数: 7, 销量均值: 1.5

    [步骤 2] 在 AI 服务离线后（通过关闭 AI 后台微服务进程），请求同一预测接口...
    当前接口响应状态码: 200
    当前数据源 (source): history-fallback
    当前趋势方向: 历史销量平均兜底 (数据库降级)
    预测天数: 7, 销量均值: 0.43
    -> [PASS] 成功触发 history-fallback 降级兜底！系统在大脑离线情况下保障了高可用。
    ```
