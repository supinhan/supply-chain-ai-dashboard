import time
import hmac
import hashlib
import json
import base64

# 使用模拟的 JWT 实现验证角色控制逻辑
JWT_SECRET = "jwt-secret-key-for-test"

def base64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).replace(b'=', b'').decode('utf-8')

def base64url_decode(payload: str) -> bytes:
    padding = '=' * (4 - (len(payload) % 4))
    return base64.urlsafe_b64decode(payload + padding)

def generate_mock_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_enc = base64url_encode(json.dumps(header).encode())
    payload_enc = base64url_encode(json.dumps(payload).encode())
    
    signature_base = f"{header_enc}.{payload_enc}"
    signature = hmac.new(secret.encode(), signature_base.encode(), hashlib.sha256).digest()
    signature_enc = base64url_encode(signature)
    
    return f"{signature_base}.{signature_enc}"

def verify_mock_jwt(token: str, secret: str) -> dict:
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT token structure")
        
    header_enc, payload_enc, signature_enc = parts
    signature_base = f"{header_enc}.{payload_enc}"
    expected_signature = hmac.new(secret.encode(), signature_base.encode(), hashlib.sha256).digest()
    expected_enc = base64url_encode(expected_signature)
    
    if not hmac.compare_digest(signature_enc, expected_enc):
        raise ValueError("Invalid JWT signature")
        
    payload = json.loads(base64url_decode(payload_enc).decode())
    if payload.get("exp", 0) < time.time():
        raise ValueError("Expired JWT token")
        
    return payload

def check_permission(token: str, required_role: str) -> bool:
    try:
        payload = verify_mock_jwt(token, JWT_SECRET)
        role = payload.get("role", "guest")
        print(f"解析令牌成功！用户名: {payload.get('sub')}, 角色: {role}")
        return role == required_role or role == "admin"
    except Exception as e:
        print(f"令牌验证失败: {e}")
        return False

def run_test():
    print("=== 开始执行 TC-SEC-03 (基于角色的 JWT 鉴权逻辑测试) ===")
    
    # 1. 构造一个管理员角色的有效 JWT 令牌
    print("[步骤 1] 生成管理员有效令牌...")
    admin_payload = {
        "sub": "cai_zihao",
        "role": "admin",
        "exp": time.time() + 3600
    }
    admin_token = generate_mock_jwt(admin_payload, JWT_SECRET)
    print(f"生成的管理员 Token: {admin_token}")
    
    # 验证管理员权限
    has_perm = check_permission(admin_token, "admin")
    assert has_perm is True
    print("-> [PASS] 管理员成功获得访问授权！")

    # 2. 构造一个低权限角色的 JWT 令牌去访问敏感接口
    print("\n[步骤 2] 生成低权限角色令牌访问管理员专用资源...")
    guest_payload = {
        "sub": "guest_user",
        "role": "guest",
        "exp": time.time() + 3600
    }
    guest_token = generate_mock_jwt(guest_payload, JWT_SECRET)
    has_perm = check_permission(guest_token, "admin")
    assert has_perm is False
    print("-> [PASS] 低权限角色访问被正确拒绝拦截！")

    # 3. 构造过期令牌进行校验
    print("\n[步骤 3] 验证过期令牌拦截行为...")
    expired_payload = {
        "sub": "some_user",
        "role": "admin",
        "exp": time.time() - 10  # 10秒前已过期
    }
    expired_token = generate_mock_jwt(expired_payload, JWT_SECRET)
    has_perm = check_permission(expired_token, "admin")
    assert has_perm is False
    print("-> [PASS] 过期令牌成功被系统拦截拒签！")

if __name__ == "__main__":
    run_test()
