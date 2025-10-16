import requests
import os
import sys

# -----------------------------------------------------------------------
LOGIN_URL = "https://client.webhostmost.com/login"  # 登录URL
REDIRECT_URL = "https://client.webhostmost.com/clientarea.php" # 跳转URL
EMAIL_FIELD = "username"     # 登录表单中邮箱字段的名称
PASSWORD_FIELD = "password"  # 登录表单中密码字段的名称
# -----------------------------------------------------------------------

def parse_users(users_secret):
    """
    将 Action Secret 中 '邮箱1:密码1\n邮箱2:密码2' 的格式解析为列表。
    """
    users = []
    if not users_secret:
        print("错误：未找到 WHM_ACCOUNT 环境变量中的用户数据。")
        return users

    for line in users_secret.strip().split('\n'):
        parts = line.strip().split(':', 1)
        if len(parts) == 2:
            email = parts[0].strip()
            password = parts[1].strip()
            users.append({'email': email, 'password': password})
        else:
            print(f"警告：跳过格式错误的行: {line}")
    return users

def attempt_login(email, password):
    """
    使用 POST 请求尝试登录。
    """
    session = requests.Session()
    
    # 构造POST请求体
    payload = {
        EMAIL_FIELD: email,
        PASSWORD_FIELD: password,
    }

    print(f"尝试登录用户：{email}...")

    try:
        # 发送POST请求
        response = session.post(LOGIN_URL, data=payload, allow_redirects=True, timeout=15)
        
        # 检查最终跳转的URL或响应内容来判断是否登录成功
        if REDIRECT_URL in response.url and response.status_code == 200:
            print(f"✅ 成功登录用户 {email}。最终URL: {response.url}")
            return True
        elif response.status_code == 200:
             print(f"⚠️ 登录请求状态码为 200，但未跳转到预期页面。最终URL: {response.url}")
             print("可能需要检查页面内容或 CSRF token。")
             return False
        else:
            print(f"❌ 登录失败用户 {email}。状态码: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ 登录用户 {email} 时发生连接错误: {e}")
        return False

def main():
    # 从环境变量（由 GitHub Action Secret 传入）中获取凭证
    user_credentials_secret = os.getenv('WHM_ACCOUNT')

    if not user_credentials_secret:
        print("错误：未设置 WHM_ACCOUNT 环境变量。请在 GitHub Secrets 中配置。")
        sys.exit(1)

    users = parse_users(user_credentials_secret)

    if not users:
        print("未解析到任何用户。退出。")
        sys.exit(1)

    all_success = True
    for user in users:
        if not attempt_login(user['email'], user['password']):
            all_success = False

    if all_success:
        print("\n所有用户登录尝试成功。")
    else:
        print("\n部分或所有用户登录失败。请检查日志。")
        # 如果需要，可以在这里 sys.exit(1) 让 Action 失败

if __name__ == "__main__":
    main()
