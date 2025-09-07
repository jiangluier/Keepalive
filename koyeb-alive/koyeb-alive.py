import os
import requests
import json
import time
import logging
from typing import List, Dict, Tuple, Any, Optional

# --- 常量定义 ---
KOYEB_LOGIN_URL = "https://app.koyeb.com/v1/account/login"
REQUEST_TIMEOUT = 30  # seconds

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def validate_and_load_accounts() -> List[Dict[str, str]]:
    # 一次性检查所有必要的环境变量，尽早失败
    tg_bot_token = os.getenv("TG_BOT_TOKEN")
    tg_chat_id = os.getenv("TG_CHAT_ID")
    koyeb_accounts_env = os.getenv("KOYEB_ACCOUNTS")

    if not all([tg_bot_token, tg_chat_id, koyeb_accounts_env]):
        raise ValueError("环境变量缺失: 请确保 KOYEB_ACCOUNTS, TG_BOT_TOKEN, 和 TG_CHAT_ID 都已设置。")

    try:
        accounts = json.loads(koyeb_accounts_env)
        if not isinstance(accounts, list):
            raise ValueError("KOYEB_ACCOUNTS 环境变量必须是一个JSON数组/列表。")
        return accounts
    except json.JSONDecodeError:
        raise ValueError("KOYEB_ACCOUNTS 环境变量的JSON格式无效。")

def send_tg_message(message: str) -> Optional[Dict[str, Any]]:
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if not bot_token or not chat_id:
        logging.warning("TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过发送 Telegram 消息。")
        return None

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # 如果状态码不是2xx，则抛出HTTPError
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"发送 Telegram 消息时发生HTTP错误: {http_err}")
        logging.error(f"响应内容: {http_err.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"发送 Telegram 消息失败: {e}")
        return None

def login_to_koyeb(email: str, password: str) -> Tuple[bool, str]:
    if not email or not password:
        return False, "邮箱或密码为空"

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    payload = {
        "email": email.strip(),
        "password": password
    }

    try:
        response = requests.post(KOYEB_LOGIN_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return True, "登录成功"
    except requests.exceptions.Timeout:
        return False, "请求超时"
    except requests.exceptions.HTTPError as http_err:

        # 尝试解析API返回的具体错误信息
        try:
            error_data = http_err.response.json()
            error_message = error_data.get('error', http_err.response.text)
            return False, f"API错误 (状态码 {http_err.response.status_code}): {error_message}"
        except json.JSONDecodeError:
            return False, f"HTTP错误 (状态码 {http_err.response.status_code}): {http_err.response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"网络请求异常: {e}"

def main():
    try:
        koyeb_accounts = validate_and_load_accounts()

        if not koyeb_accounts:
            raise ValueError("环境变量 KOYEB_ACCOUNTS 解析后为空列表。")

        results = []
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        total_accounts = len(koyeb_accounts)
        success_count = 0

        for index, account in enumerate(koyeb_accounts, 1):
            email = account.get('email', '').strip()
            password = account.get('password', '')

            if not email or not password:
                logging.warning(f"第 {index}/{total_accounts} 个账户信息不完整，已跳过。")
                results.append(f"账户: 未提供邮箱\n状态: ❌ 信息不完整\n")
                continue

            logging.info(f"正在处理第 {index}/{total_accounts} 个账户: {email}")
            time.sleep(8)  # 保持登录间隔，防止触发速率限制

            try:
                success, message = login_to_koyeb(email, password)
                if success:
                    status_line = f"状态: ✅ {message}"
                    success_count += 1
                else:
                    status_line = f"状态: ❌ 登录失败\n原因：{message}"
            except Exception as e:
                # 捕获 login_to_koyeb 内部未预料到的异常
                logging.error(f"处理账户 {email} 时发生未知异常: {e}")
                status_line = f"状态: ❌ 登录失败\n原因：执行时发生未知异常 - {e}"

            results.append(f"账户: `{email}`\n{status_line}\n")

        summary = f"📊 总计: {total_accounts} 个账户\n✅ 成功: {success_count} 个 | ❌ 失败: {total_accounts - success_count} 个\n"
        # 使用 join 方法构建最终消息，更高效
        report_body = "".join(results)
        tg_message = f"🤖 **Koyeb 登录状态报告**\n\n⏰ **检查时间**: {current_time}\n\n{summary}\n{report_body}"

        logging.info("--- 报告预览 ---\n" + tg_message)
        send_tg_message(tg_message)
        logging.info("脚本执行完毕。")

    except Exception as e:
        # 捕获启动阶段的错误 (如环境变量验证失败)
        error_message = f"❌ 程序初始化失败: {e}"
        logging.error(error_message)
        send_tg_message(error_message)

if __name__ == "__main__":
    main()
