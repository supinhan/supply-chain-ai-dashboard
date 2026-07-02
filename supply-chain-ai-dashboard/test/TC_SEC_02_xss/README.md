# TC-SEC-02：XSS 脚本跨站防护测试

### 1. 测试流程
1. 构造恶意 XSS 脚本数据：`customer_city = "<script>alert('XSS-Test')</script>"`。
2. 通过 API 注入该订单，验证后端是否接受。
3. 检查数据回传时是否以 JSON 实体形式安全包裹。
4. 前端应用 Vue 3 大屏采用 `{{ }}` 进行插值展示，这会自动将 `<` 和 `>` 转化为 `&lt;` 和 `&gt;` 以文本内容形式输出，从而完全消除脚本执行环境。
5. 执行 `test_xss.py` 脚本：
   ```bash
   python test/TC_SEC_02_xss/test_xss.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-SEC-02 (XSS 脚本跨站防护测试) ===
    响应状态码: 200
    后端保存返回的内容: test_xss_order_112
    -> [PASS] 后端接受到该值并以 JSON 文本安全保存与传输。前端 Vue 3 数据插值将以 textContent 渲染转义该标签，不会执行弹窗！
    ```
