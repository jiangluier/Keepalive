import requests
import os
import sys
import re

# -----------------------------------------------------------------------
BASE_URL = "https://client.webhostmost.com"
LOGIN_URL = f"{BASE_URL}/login"  # 登录页
REDIRECT_URL = f"{BASE_URL}/clientarea.php"  # 登录成功后跳转页
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


def get_csrf_token(session):
    """
    访问登录页，提取 CSRF token。
    """
    try:
        r = session.get(LOGIN_URL, timeout=15)
        r.raise_for_status()

        # 匹配 hidden input 中的 token 值
        match = re.search(r'name="token"\s+value="([^"]+)"', r.text)
        if match:
            token = match.group(1)
            print(f"✅ 获取到 CSRF Token: {token[:8]}...")
            return token
        else:
            print("⚠️ 未找到 CSRF Token，可能页面结构已变。")
            return None
    except requests.RequestException as e:
        print(f"❌ 获取登录页时出错: {e}")
        return None


def attempt_login(email, password):
    """
    使用 POST 请求尝试登录。
    """
    session = requests.Session()

    print(f"\n尝试登录用户：{email}...")

    # 先获取 token
    token = get_csrf_token(session)
    if not token:
        print("⚠️ 获取 CSRF Token 失败，跳过此账号。")
        return False

    # 构造POST请求体
    payload = {
        EMAIL_FIELD: email,
        PASSWORD_FIELD: password,
        "token": token,
        "rememberme": "on",  # 有些站点需要带这个字段
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": LOGIN_URL,
        "Origin": BASE_URL,
    }

    try:
        response = session.post(LOGIN_URL, data=payload, headers=headers, allow_redirects=True, timeout=15)

        # 判断是否登录成功
        if REDIRECT_URL in response.url:
            print(f"✅ 成功登录用户 {email}。跳转到: {response.url}")
            return True
        elif "clientarea.php" in response.text.lower():
            print(f"✅ 成功登录用户 {email}（检测到 clientarea 内容）")
            return True
        elif response.status_code == 200 and "Invalid CSRF token" in response.text:
            print(f"❌ 登录失败：Token 无效。用户 {email}")
            return False
        elif response.status_code == 200 and "incorrect" in response.text.lower():
            print(f"❌ 登录失败：账号或密码错误。用户 {email}")
            return False
        else:
            print(f"⚠️ 登录请求状态码为 {response.status_code}，未检测到成功标识。URL: {response.url}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ 登录用户 {email} 时发生连接错误: {e}")
        return False


def main():
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


if __name__ == "__main__":
    main()
