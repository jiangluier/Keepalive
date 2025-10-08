#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

此脚本提取多个账号的 Cookie 令牌，并将其保存为包含账号名称的 JSON 格式，
供多账号签到脚本 checkin_token.py 使用。

用法:
    python get_tokens_helper.py
    
GitHub Actions: 设置 LEAFLOW_COOKIES 环境变量，格式为 "名称|Cookie\n名称2|Cookie2"
本地测试: 在脚本中硬编码测试 Cookie 字符串
"""

import json
import os
from urllib.parse import unquote
import sys

# 定义多账号分隔符和名称-Cookie分隔符
ACCOUNT_DELIMITER = '\n'  # 账号间使用换行符分隔
NAME_COOKIE_SEPARATOR = '|' # 名称和 Cookie 之间使用竖线分隔

def parse_cookie_string(cookie_string):
    cookies = {}
    
    # Split by semicolon and process each cookie
    for cookie in cookie_string.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            # Split only on first = to handle values with =
            name, value = cookie.split('=', 1)
            cookies[name.strip()] = value.strip()
    
    return cookies

def create_config_from_accounts_data(accounts_data):
    accounts = []
    
    # 循环遍历所有账号数据，构建 accounts 列表
    for data in accounts_data:
        # data["cookies"] 是解析后的 cookie 字典
        if data["cookies"]: 
            account_entry = {
                "name": data["name"], 
                "token_data": {
                    "cookies": data["cookies"]
                }
            }
            accounts.append(account_entry)

    # 构建最终配置
    config = {
        "settings": {
            "log_level": "INFO",
            "retry_delay": 5, # 增加延迟，避免多账号操作过快
            "timeout": 30,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        },
        "accounts": accounts
    }
    
    return config

def main():
    # 1. 从环境变量 LEAFLOW_COOKIES 获取原始 cookies 字符串
    raw_cookie_string = os.environ.get('LEAFLOW_COOKIES', '')
    
    # For local testing: Hardcoded multi-account string
    if not raw_cookie_string:
        # 在本地测试时，请使用 "名称|Cookie" 格式，并用换行符分隔
        raw_cookie_string = """张三|cookie_string_for_zhangsan_key1=value1;key2=value2
李四|cookie_string_for_lisi_sessionid=xyz123;userid=456"""
    
    if not raw_cookie_string or 'your_cookie_string_here' in raw_cookie_string:
        print("❌  未提供有效的 Cookie 字符串！")
        print(f"请在 LEAFLOW_COOKIES 中设置 '名称{NAME_COOKIE_SEPARATOR}Cookie'，并用换行符分隔。")
        return False
    
    # 按换行符分割成单行的账号数据
    account_strings = [s.strip() for s in raw_cookie_string.split(ACCOUNT_DELIMITER) if s.strip()]
    
    if not account_strings:
        print("❌ 分割后未找到任何有效的账号条目！")
        return False

    print(f"📝 找到 {len(account_strings)} 个账号数据。正在解析...")
    
    all_accounts_data = []
    
    # 循环解析每个账号
    for i, account_str in enumerate(account_strings):
        # 将每个账号的名称和 cookie 分离
        parts = account_str.split(NAME_COOKIE_SEPARATOR, 1)
        
        if len(parts) != 2:
            name = f"账号 {i + 1} (解析失败)"
            print(f"⚠️ 警告: 账号 {i+1} 格式错误，已跳过：{account_str[:30]}...")
            continue
            
        name, single_cookie_string = parts[0].strip(), parts[1].strip()
        
        # 解析 Cookie
        cookies = parse_cookie_string(single_cookie_string)
        
        if cookies:
            all_accounts_data.append({
                "name": name,
                "cookies": cookies
            })
            
            # 显示找到的 cookies
            print(f"\n✅ 成功解析账号: {name}")
            print(f"\n✅ 找到 {len(cookies)} 个 Cookie:")
            for c_name in cookies.keys():
                value_preview = cookies[c_name][:20] + "..." if len(cookies[c_name]) > 20 else cookies[c_name]
                print(f"   - {c_name}: {value_preview}")
        else:
            print(f"\n⚠️ 警告: 未找到账号 {name} 的任何 Cookie。已跳过。")

    if not all_accounts_data:
        print("\n❌ 无法解析出任何账号的有效 Cookie。正在退出。")
        return False
    
    # 创建配置结构
    config = create_config_from_accounts_data(all_accounts_data)
    
    # 保存到文件
    output_file = "config.accounts.json"
    print(f"\n💾 正在保存 {len(all_accounts_data)} 个账号的配置到 {output_file}...")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"❌ 写入配置文件失败: {e}")
        return False
        
    print(f"✅ 配置已成功保存！")
    print(f"📄 您现在可以运行: python checkin_token.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
