import sys
import os
import json
from pathlib import Path

# 将 data_producer 路径添加到 path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data_producer')))

from replay_script import read_checkpoint, write_checkpoint

def run_test():
    print("=== 开始执行 TC-FUNC-01 (流式订单回放与断点续传测试) ===")
    
    checkpoint_dir = Path(__file__).parent / "temp_runtime"
    checkpoint_dir.mkdir(exist_ok=True)
    checkpoint_path = checkpoint_dir / "replay_checkpoint.json"

    if checkpoint_path.exists():
        os.remove(checkpoint_path)

    # 1. 验证没有 checkpoint 时的读取行为
    print("[步骤 1] 校验空 checkpoint 读取...")
    row = read_checkpoint(checkpoint_path)
    assert row is None
    print("-> [PASS] 空 checkpoint 返回 None 正确！")

    # 2. 验证写入 checkpoint 行号
    print("\n[步骤 2] 写入并读取 checkpoint 行号...")
    write_checkpoint(checkpoint_path, 42, "ORD_12345")
    row = read_checkpoint(checkpoint_path)
    assert row == 42
    print(f"-> [PASS] 成功恢复行号: {row}！")

    # 3. 校验真实数据源结构
    print("\n[步骤 3] 验证 DataCo 数据集是否存在...")
    csv_dir = Path(__file__).resolve().parents[2] / "data_producer" / "dataset"
    csv_files = list(csv_dir.glob("*.csv"))
    if csv_files:
        print(f"-> [PASS] 找到数据集文件: {[f.name for f in csv_files]}")
    else:
        print("-> [WARNING] 未在 data_producer/dataset 找到 CSV 文件，可能是空挂载。")

    # 清理临时文件
    if checkpoint_path.exists():
        os.remove(checkpoint_path)
    os.rmdir(checkpoint_dir)

if __name__ == "__main__":
    run_test()
