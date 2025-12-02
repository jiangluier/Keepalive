import os
import sys
import asyncio
import requests
from telethon import TelegramClient
from telethon.tl.custom.message import Message
from typing import Dict, Any

# Windows 事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TG_CHANNEL = os.getenv('TG_CHANNEL', '@cloudcatgroup')     # 签到目标频道名或 @username
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN') # 你的通知机器人 Token
TG_CHAT_ID = os.getenv('TG_CHAT_ID')     # 你的个人或群组 Chat ID
TG_NAME = "yutian-青云志"                 # 你的TG用户名/昵称 (用于匹配机器人回复)
CHANNEL_BOT_ID = 7694509436              # @CloudCatOfficialBot 的用户 ID
CHECK_WAIT_TIME = 20                     # 等待机器人回复的时间（秒）
# ============================================

# 定义颜色和符号 (用于日志美化)
COLORS: Dict[str, str] = {
    'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
    'blue': '\033[94m', 'magenta': '\033[95m', 'cyan': '\033[96m',
    'white': '\033[97m', 'reset': '\033[0m'
}
SYMBOLS: Dict[str, str] = {'check': '✓', 'warning': '⚠', 'arrow': '➜', 'error': '✗'}

def log(color: str, symbol: str, message: str):
    """日志函数"""
    print(f"{COLORS[color]}{SYMBOLS[symbol]} {message}{COLORS['reset']}")

def send_tg_notification(status: str, message: str):
    """发送 Telegram 消息通知"""
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return

    emoji = "✅" if status == "成功" else "❌"
    notification_text = f"*CloudCat 签到任务通知*\n\n状态：{emoji} {status}\n频道：`{TG_CHANNEL}`\n详情：{message}"
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload: Dict[str, Any] = {
        'chat_id': TG_CHAT_ID,
        'text': notification_text,
        'parse_mode': 'Markdown'
    }

    try:
        requests.post(url, data=payload, timeout=10).raise_for_status()
    except requests.exceptions.RequestException as e:
        log('red', 'error', f"Telegram 通知发送失败: {e}")

async def check_in():
    """执行频道签到并判断结果的主逻辑"""
    
    # 检查核心登录变量
    required_vars = {'TG_API_ID': TG_API_ID, 'TG_API_HASH': TG_API_HASH}
    missing_vars = [name for name, val in required_vars.items() if not val]
    
    if missing_vars:
        err_msg = f"核心登录失败：缺少必要的配置变量: {', '.join(missing_vars)}！请检查 GitHub Secrets 设置"
        log('red', 'error', err_msg)
        send_tg_notification("失败", err_msg)
        sys.exit(1) # 缺少关键Secrets，强制退出

    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tg_session.session')
    
    log('cyan', 'arrow', "启动 Telegram 客户端并尝试以您的身份登录")
    
    try:
        async with TelegramClient(session_path, TG_API_ID, TG_API_HASH) as client:
            await client.start()
            
            # 1. 成功关键词直接使用 TG_NAME
            SUCCESS_KEYWORD = TG_NAME
            log('cyan', 'arrow', f"成功判断关键词设置为: '{SUCCESS_KEYWORD}'")

            # 2. 连接频道
            channel_entity = await client.get_entity(TG_CHANNEL)
            log('cyan', 'arrow', f"已成功连接频道：{channel_entity.title}")

            # 3. 发送签到命令
            log('cyan', 'arrow', "发送签到命令 /checkin")
            sent_message = await client.send_message(channel_entity, '/checkin')
            log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒，寻找机器人回复")
            await asyncio.sleep(CHECK_WAIT_TIME)
            
            # 4. 检查最新的消息
            is_success = False
            check_limit = 5 # 检查最近5条消息

            # 遍历最新的消息
            async for msg in client.iter_messages(channel_entity, limit=check_limit):
                # 检查发送者是否为目标机器人
                if isinstance(msg, Message) and msg.sender_id == CHANNEL_BOT_ID:        
                    # 检查 Bot 的回复内容是否包含 TG_NAME
                    if msg.text and SUCCESS_KEYWORD in msg.text:
                        is_success = True
                        break

            # 5. 处理结果
            if is_success:
                final_msg = f"签到成功！机器人（ID: {CHANNEL_BOT_ID}）回复中包含您的用户名：'{SUCCESS_KEYWORD}'"
                log('green', 'check', final_msg)
                send_tg_notification("成功", final_msg)
            else:
                final_msg = "签到失败或无法确认。未在最新消息中找到来自机器人的、包含您用户名的成功回复"
                log('red', 'error', final_msg)
                send_tg_notification("失败", final_msg)

    except Exception as e:
        err_msg = f"连接或执行过程中出现严重错误: {type(e).__name__} - {str(e)}"
        log('red', 'error', err_msg)
        send_tg_notification("失败", err_msg)
        log('yellow', 'warning', "请检查 API 配置、频道名称是否正确，或尝试删除旧的 session 文件重新登录")
        sys.exit(1) # 强制退出，使 GitHub Action 失败

if __name__ == '__main__':
    log('cyan', 'arrow', "开始执行频道签到任务...")
    asyncio.run(check_in())
    log('green', 'check', "任务结束")
