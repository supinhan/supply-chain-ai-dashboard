import sys
import os
from sqlalchemy import select

# 将项目路径及 backend_api 路径加入 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend_api')))

from backend_api.app.db.database import SessionLocal, AlertRecord

def run_test():
    print("=== 开始执行 TC-FUNC-08 (数据库告警状态确认/ACK 逻辑测试) ===")
    
    session = SessionLocal()
    try:
        # 1. 查询数据库中现有的告警记录
        print("[步骤 1] 查询数据库中所有未确认的告警记录...")
        stmt = select(AlertRecord).where(AlertRecord.status == 0)
        alerts = session.scalars(stmt).all()
        print(f"找到 {len(alerts)} 条未确认的告警。")
        
        if not alerts:
            print("-> [WARNING] 未在数据库中找到未确认告警，测试用例跳过。请确保先前已注入高风险订单。")
            return
            
        target_alert = alerts[0]
        alert_id = target_alert.id
        print(f"目标告警 ID: {alert_id}, 订单 ID: {target_alert.order_id}, 初始状态: {target_alert.status}")
        
        # 2. 模拟 ACK 动作：修改状态为 1 (已确认)
        print("\n[步骤 2] 修改告警状态为已确认 (status = 1) 并提交事务...")
        target_alert.status = 1
        session.commit()
        print("事务提交成功！")
        
        # 3. 重新获取告警状态验证是否成功持久化
        print("\n[步骤 3] 从数据库重新查询该告警以确认状态已持久化...")
        session.expire(target_alert)
        updated_alert = session.get(AlertRecord, alert_id)
        print(f"查询到更新后的状态: {updated_alert.status}")
        
        assert updated_alert.status == 1
        print(f"-> [PASS] 告警 ID {alert_id} 成功被确认为 ACK 态 (status=1)！数据库更新功能验证通过。")
        
    except Exception as e:
        session.rollback()
        print(f"-> [FAIL] 数据库更新异常: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    run_test()
