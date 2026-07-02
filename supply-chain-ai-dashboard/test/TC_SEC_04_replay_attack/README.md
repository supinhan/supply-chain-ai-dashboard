# TC-SEC-04：防重放攻击与过期机制测试

### 1. 测试流程
1. 重放防护原理：后端接口开启 `X-SCAI-Timestamp` 校验，在 `backend_api/app/core/security.py` 中限时时间窗口为 300 秒（`max_age_seconds=300`）。
2. 构造一个历史（1 小时前）已经生成的合法签名头部。
3. 重放该请求，验证服务端是否拦截并提示 `"Expired request signature"`。
4. 执行 `test_replay_attack.py` 脚本：
   ```bash
   python test/TC_SEC_04_replay_attack/test_replay_attack.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-SEC-04 (防重放攻击与过期机制测试) ===
    [步骤 1] 携带 1 小时前的历史合法签名进行重放请求...
    响应状态码: 401, 内容: {"detail":"Expired request signature"}
    -> [PASS] 重放请求由于时间窗过期被成功拦截拒签！
    ```
