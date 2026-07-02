import asyncio
import websockets
import json

URL = "ws://127.0.0.1:8000/api/v1/ws/alerts"

async def test_websocket():
    print("=== 开始执行 TC-FUNC-05 (WebSocket 实时广播与数据推送测试) ===")
    print(f"正在建立连接到 {URL} ...")
    
    try:
        async with websockets.connect(URL) as ws:
            print("WebSocket 握手成功！等待接收第一帧消息...")
            
            # 接收第一帧，通常是 stats
            message = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(message)
            print(f"收到帧消息类型: {data.get('type')}")
            
            # 验证类型为 stats 且字段完整 (使用 camelCase)
            assert data.get("type") == "stats"
            stats = data.get("data", {})
            assert "totalOrders" in stats
            assert "gmv" in stats
            assert "riskCount" in stats
            print(f"-> [PASS] 成功接收 stats 数据，当前订单总数: {stats['totalOrders']}, GMV: {stats['gmv']}")
            
    except Exception as e:
        print(f"-> [FAIL] WebSocket 测试异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
