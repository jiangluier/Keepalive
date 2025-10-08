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
    with mutex:
        _print(text, *args, **kw)

# 通知服务配置
push_config = {
    'HITOKOTO': True,
    'CONSOLE': True,
    'QYWX_KEY': '',  # WeChat Work webhook key
    'TG_BOT_TOKEN': '',  # Telegram bot API token
    'TG_CHAT_ID': ''  # Telegram chat ID
}

# 从环境变量加载配置
for k in push_config:
    if os.getenv(k):
        push_config[k] = os.getenv(k)

def telegram_bot(title: str, content: str) -> None:
    print("正在启动 TG 机器人...")
    
    token = push_config.get("TG_BOT_TOKEN")
    chat_id = push_config.get("TG_CHAT_ID")
    
    if not token or not chat_id:
        print("缺少TG配置参数，请检查TG_BOT_TOKEN和TG_CHAT_ID!")
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
            print("TG 机器人消息推送成功！")
        else:
            print(f"TG机器人推送失败! 错误: {result.get('description')}")
    except Exception as e:
        print(f"TG机器人推送异常: {e}")

def wecom_bot(title: str, content: str) -> None:
    print("企业微信机器人服务启动...")
    
    key = push_config.get("QYWX_KEY")
    if not key:
        print("缺少企业微信推送配置，请查看环境变量 QYWX_KEY")
        return
    
    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    headers = {"Content-Type": "application/json;charset=utf-8"}
    data = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}
    
    try:
        response = requests.post(
            url=url, data=json.dumps(data), headers=headers, timeout=15
        ).json()

        if response.get("errcode") == 0:
            print("企业微信机器人消息推送成功!")
        else:
            print(f"企业微信机器人推送失败！错误代码：{Response.get（'errcode'）}，错误消息：{response.get（'errmsg'）}")
    except Exception as e:
        print(f"企业微信机器人推送异常: {e}")

def one() -> str:
    url = "https://v1.hitokoto.cn/"
    try:
        res = requests.get(url, timeout=10).json()
        return res["hitokoto"] + "    ----" + res["from"]
    except Exception as e:
        print(f"Hitokoto 获取失败: {e}")
        return "Hitokoto 获取失败"

def console(title: str, content: str) -> None:
    print(f"{title}\n\n{content}")

def add_notify_function():
    notify_function = []
    
    if push_config.get("CONSOLE"):
        notify_function.append(console)
    
    if push_config.get("QYWX_KEY"):
        notify_function.append(wecom_bot)
    
    if push_config.get("TG_BOT_TOKEN") and push_config.get("TG_CHAT_ID"):
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
        print(f"{title} 推送内容为空！")
        return

    # 根据标题跳过推送，环境变量：SKIP_PUSH_TITLE，以换行符分隔
    skipTitle = os.getenv("SKIP_PUSH_TITLE")
    if skipTitle:
        if title in re.split("\n", skipTitle):
            print(f"{title} 位于 SKIP_PUSH_TITLE 环境变量中，跳过推送！")
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
    print("正在进行通知测试...")
    send("测试标题”，“这是通知测试。如果收到此消息，则通知配置成功！")
    print("通知请求完成！")

if __name__ == "__main__":
    main()
