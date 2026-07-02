# TC-FUNC-02：API 安全签名与篡改校验测试

### 1. 测试流程
1. 后端接口开启 `X-SCAI-API-Key` 与 HMAC-SHA256 签名机制。
2. 分别模拟发送：
   *   无签名的未授权请求。
   *   签名正常但修改了订单金额的篡改请求。
   *   10分钟前的过期签名请求。
   *   正确计算签名的合法请求。
3. 执行 `test_hmac.py` 脚本：
   ```bash
   python test/TC_FUNC_02_api_hmac/test_hmac.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-FUNC-02 (API 安全签名与篡改校验测试) ===

    [步骤 1] 发送未带签名的请求...
    响应状态码: 401, 返回内容: {"detail":"Invalid API key"}
    -> [PASS] 无签名请求成功被拦截！

    [步骤 2] 发送修改内容但未更新签名的请求 (篡改数据)...
    响应状态码: 401, 返回内容: {"detail":"Invalid request signature"}
    -> [PASS] 数据篡改请求成功被拦截！

    [步骤 3] 发送过期签名的请求 (10分钟前的时间戳)...
    响应状态码: 401, 返回内容: {"detail":"Expired request signature"}
    -> [PASS] 过期请求成功被拦截！

    [步骤 4] 发送合法且正确签名的请求...
    响应状态码: 200, 返回内容: {"status":"success","order_id":"test_order_hmac_001","risk_score":0.2897,"is_high_risk":false,"alert":null}
    -> [PASS] 合法签名请求成功注入！
    ```
