# TC-SEC-01：SQL 注入防御测试

### 1. 测试流程
1. 类型安全检查：请求 `GET /kpi/history?hours=1' OR '1'='1`。FastAPI 校验框架自动识别 hours 格式不合符 `int`，直接拦截并返回 `422 Unprocessable Entity`。
2. 转义安全性检查：POST 注入 payload 中携带 `customer_city = "Chicago' OR '1'='1 --"`。通过 SQLAlchemy ORM 参数化绑定，校验其是否作为纯字符串值入库。
3. 执行 `test_sql_injection.py` 脚本：
   ```bash
   python test/TC_SEC_01_sql_injection/test_sql_injection.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-SEC-01 (SQL 注入防御测试) ===
    [步骤 1] 校验类型限制参数 SQL 注入拦截 (GET /kpi/history?hours=1' OR '1'='1)...
    响应状态码: 422, 内容: {"detail":[{"type":"int_parsing","loc":["query","hours"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"1' OR '1'='1","url":"https://errors.pydantic.dev/2.5/v/int_parsing"}]}
    -> [PASS] 类型不符的 SQL 注入成功在入口层校验拦截！

    [步骤 2] 校验字符型字段 SQL 注入转义 (POST /stream/ingest)...
    响应状态码: 200, 内容: {"status":"success","order_id":"test_sql_inject_001","risk_score":0.2568,"is_high_risk":false,"alert":null}
    -> [PASS] ORM 参数绑定已自动安全转义，订单成功以纯文本值保存！
    ```
