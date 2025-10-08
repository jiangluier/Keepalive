#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import re
import threading
import requests

_print = print
mutex = threading.Lock()

def print(text, *args, **kw):
    """
    Thread-safe print function to prevent output corruption.
    """
    with mutex:
        _print(text, *args, **kw)

# Notification service configuration
push_config = {
    'HITOKOTO': True,
    'CONSOLE': True,
    'QYWX_KEY': '',  # WeChat Work webhook key
    'TG_BOT_TOKEN': '',  # Telegram bot API token
    'TG_USER_ID': ''  # Telegram user ID
}

# Load configuration from environment variables
for k in push_config:
    if os.getenv(k):
        push_config[k] = os.getenv(k)

def telegram_bot(title: str, content: str) -> None:
    """
    Send notification via Telegram bot.
    """
    print("Telegram bot service starting")
    
    token = push_config.get("TG_BOT_TOKEN")
    chat_id = push_config.get("TG_USER_ID")
    
    if not token or not chat_id:
        print("Telegram configuration missing, please check TG_BOT_TOKEN and TG_USER_ID!")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": f"{title}\n\n{content}",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url=url, data=data, timeout=30)
        result = response.json()
        
        if result.get("ok"):
            print("Telegram bot push successful!")
        else:
            print(f"Telegram bot push failed! Error: {result.get('description')}")
    except Exception as e:
        print(f"Telegram bot push exception: {e}")

def wecom_bot(title: str, content: str) -> None:
    """
    Send notification via WeChat Work bot.
    """
    print("WeChat Work bot service starting")
    
    key = push_config.get("QYWX_KEY")
    if not key:
        print("WeChat Work configuration missing, please check QYWX_KEY!")
        return
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}
    
    try:
        response = requests.post(
            url=url, data=json.dumps(data), headers=headers, timeout=15
        ).json()

        if response.get("errcode") == 0:
            print("WeChat Work bot push successful!")
        else:
            print(f"WeChat Work bot push failed! Error code: {response.get('errcode')}, Error message: {response.get('errmsg')}")
    except Exception as e:
        print(f"WeChat Work bot push exception: {e}")

def one() -> str:
    """
    Get a random sentence from Hitokoto API.
    """
    url = "https://v1.hitokoto.cn/"
    try:
        res = requests.get(url, timeout=10).json()
        return res["hitokoto"] + "    ----" + res["from"]
    except Exception as e:
        print(f"Hitokoto fetch failed: {e}")
        return "Hitokoto fetch failed"

def console(title: str, content: str) -> None:
    """
    Print notification to console.
    """
    print(f"{title}\n\n{content}")

def add_notify_function():
    """Add all notification functions"""
    notify_function = []
    
    if push_config.get("CONSOLE"):
        notify_function.append(console)
    
    if push_config.get("QYWX_KEY"):
        notify_function.append(wecom_bot)
    
    if push_config.get("TG_BOT_TOKEN") and push_config.get("TG_USER_ID"):
        notify_function.append(telegram_bot)

    return notify_function

def send(title: str, content: str, ignore_default_config: bool = False, **kwargs):
    if kwargs:
        global push_config
        if ignore_default_config:
            push_config = kwargs
        else:
            push_config.update(kwargs)

    if not content:
        print(f"{title} Push content is empty!")
        return

    # Skip push based on title, environment variable: SKIP_PUSH_TITLE separated by newline
    skipTitle = os.getenv("SKIP_PUSH_TITLE")
    if skipTitle:
        if title in re.split("\n", skipTitle):
            print(f"{title} is in SKIP_PUSH_TITLE environment variable, skipping push!")
            return

    # Add Hitokoto
    hitokoto = push_config.get("HITOKOTO")
    if hitokoto and hitokoto != "false":
        content += "\n\n" + one()

    # Execute notification functions
    notify_function = add_notify_function()
    
    ts = [
        threading.Thread(target=mode, args=(title, content), name=mode.__name__)
        for mode in notify_function
    ]
    [t.start() for t in ts]
    [t.join() for t in ts]

def main():
    print("Starting test notification...")
    send("Test Title", "This is a notification test. If you receive this, the notification configuration is successful!")
    print("Notification request completed")

if __name__ == "__main__":
    main()