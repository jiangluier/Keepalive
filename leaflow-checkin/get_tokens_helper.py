#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from urllib.parse import unquote

# 定义分隔符，使用换行符 '\n'
COOKIE_DELIMITER = '\n'

def parse_cookie_string(cookie_string):
    cookies = {}
    
    # 按分号拆分并处理每个cookie
    for cookie in cookie_string.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            # Split only on first = to handle values with =
            name, value = cookie.split('=', 1)
            cookies[name.strip()] = value.strip()
    
    return cookies

def create_config_from_cookies_list(cookies_list):
    accounts = []
    
    # 循环遍历所有账号的 cookies
    for cookies in cookies_list:
        if cookies:
            account_entry = {
                "token_data": {
                    "cookies": cookies
                }
            }
            accounts.append(account_entry)

    # 构建最终配置
    config = {
        "settings": {
            "log_level": "INFO",
            "retry_delay": 5,
            "timeout": 30,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        },
        "accounts": accounts
    }
    
    return config

def main():
    # 从环境变量 LEAFLOW_COOKIES 读取原始 cookies 字符串
    raw_cookie_string = os.environ.get('LEAFLOW_COOKIES', '')
    
    # 用于本地测试：硬编码cookie字符串
    if not raw_cookie_string:
        raw_cookie_string = """your_cookie_string_here_account1
your_cookie_string_here_account2"""
    
    if not raw_cookie_string or raw_cookie_string.strip() == 'your_cookie_string_here':
        print("❌ 没有提供有效的cookie字符串！")
        print("对于GitHub操作：设置LEAFLOW_COOKIES环境变量，其中多个cookie字符串换行分隔")
        print("对于本地测试：将多个cookie字符串换行分隔")
        return False
    
    # 按分隔符（换行符）分割成单个账号的 cookie 字符串列表
    cookie_strings = [s.strip() for s in raw_cookie_string.split(COOKIE_DELIMITER) if s.strip()]
    
    if not cookie_strings:
        print("❌ 拆分后未找到有效的cookie字符串！")
        return False

    print(f"📝 发现 {len(cookie_strings)} 账号的字符串. 正在解析...")
    
    all_accounts_cookies = []
    
    # 循环解析每个账号的 cookie 字符串
    for i, single_cookie_string in enumerate(cookie_strings):
        account_name = f"账号 {i + 1}"
        print(f"\n--- Parsing {account_name} ---")
        
        # 解析单个 cookie 字符串
        cookies = parse_cookie_string(single_cookie_string)
        
        if cookies:
            all_accounts_cookies.append(cookies)
            
            # 显示找到的 cookies
            print(f"✅ Found {len(cookies)} cookies for {account_name}:")
            for name in cookies.keys():
                # Show first few chars of value for verification (masked for security)
                value_preview = cookies[name][:20] + "..." if len(cookies[name]) > 20 else cookies[name]
                print(f"  - {name}: {value_preview}")
        else:
            print(f"⚠️ 警告: 未找到 {account_name} 账号的cookie。跳过...")

    if not all_accounts_cookies:
        print("\n❌ 无法解析任何帐户的cookie。退出...")
        return False
    
    # 创建配置结构
    config = create_config_from_cookies_list(all_accounts_cookies)
    
    # 保存到文件
    output_file = "config.accounts.json"
    print(f"\n💾 为 {len(all_accounts_cookies)} 账号保存配置到 {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 配置保存成功！")
    print(f"📄 现在可以运行：pythoncheckin_token.py")
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
