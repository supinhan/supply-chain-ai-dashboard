# TC-FUNC-03：双模 AI 预警机制测试

### 1. 测试流程
1. 校验亏损拦截规则：注入一条 `profit_ratio = -0.2` (亏损) 的订单，验证后端是否直接拦截，限制风险分在 `0.90 ~ 0.985` 之间。
2. 校验模型打分：注入一条正常盈利订单，检查机器学习模型对其推理输出的风险得分。
3. 执行 `test_ai_risk.py` 脚本：
   ```bash
   python test/TC_FUNC_03_ai_risk/test_ai_risk.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-FUNC-03 (双模 AI 预警机制与 XAI 可解释归因测试) ===

    [测试用例 1] 注入负利润亏损订单 (触发规则硬拦截)...
    响应状态码: 200
    返回结果: {
      "status": "success",
      "order_id": "test_order_loss_999",
      "risk_score": 0.985,
      "is_high_risk": true,
      "alert": {
        "id": 14,
        "order_id": "test_order_loss_999",
        "risk_type": "供应链高欺诈/异常风险",
        "probability": 0.985,
        "status": 0,
        "timestamp": "2026-07-02T14:15:19.837121",
        "xai_analysis": {
          "订单利润": 0.757,
          "订单总额": 0.202,
          "运输模式": 0.041
        }
      }
    }
    -> [PASS] 负利润硬拦截规则测试成功！XAI 归因包含 订单利润 权重。

    [测试用例 2] 注入正常盈利订单 (进入机器学习打分)...
    响应状态码: 200
    返回结果: {
      "status": "success",
      "order_id": "test_order_normal_001",
      "risk_score": 0.3625,
      "is_high_risk": false,
      "alert": null
    }
    -> [PASS] 普通正常盈利订单推理测试成功！模型返回了风险分值。
    ```
