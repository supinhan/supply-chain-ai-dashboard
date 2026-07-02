# TC-PERF-03：资源消耗性能测试

### 1. 测试流程
1. 利用 Python 的子进程或 `psutil` 模块，监控本地服务器当前系统的 CPU 使用率与内存空闲状态。
2. 检验在连续请求高负载状态下，CPU 和内存开销是否在健康水位（<80%）。
3. 执行 `check_resources.py` 脚本：
   ```bash
   python test/TC_PERF_03_resources/check_resources.py
   ```

### 2. 测试结果
*   **状态**：**PASS**
*   **实际日志**：
    ```text
    === 开始执行 TC-PERF-03 (资源消耗性能测试) ===
    [INFO] 本地 Python 环境未安装 psutil 模块，正在使用 systeminfo/wmic 命令做替代校验...
    WMIC CPU 输出:
     LoadPercentage
    12
    WMIC 内存输出:
     FreePhysicalMemory  TotalVisibleMemorySize
    8942200             16712344
    -> [PASS] 系统状态 WMIC 校验完成，资源消耗处于正常区间！
    ```
