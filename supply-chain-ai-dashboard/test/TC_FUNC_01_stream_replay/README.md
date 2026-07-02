# TC-FUNC-01：流式订单回放与断点续传测试

### 1. 测试流程
1. 在 `data_producer/replay_script.py` 中，读取数据回放配置及 `dataset` 数据集文件。
2. 校验在无断点时，读取断点文件返回空；写入临时断点（如行号 42），再次读取，验证行号是否可复原。
3. 执行 `test_replay.py` 脚本：
   ```bash
   python test/TC_FUNC_01_stream_replay/test_replay.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-FUNC-01 (流式订单回放与断点续传测试) ===
    [步骤 1] 校验空 checkpoint 读取...
    -> [PASS] 空 checkpoint 返回 None 正确！

    [步骤 2] 写入并读取 checkpoint 行号...
    -> [PASS] 成功恢复行号: 42！

    [步骤 3] 验证 DataCo 数据集是否存在...
    -> [PASS] 找到数据集文件: ['DataCoSupplyChainDataset.csv', 'DescriptionDataCoSupplyChain.csv', 'tokenized_access_logs.csv']
    ```
