import os
import sys
import asyncio
import requests
from telethon import TelegramClient
from telethon.tl.custom.message import Message

# Windows 事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
CHANNEL = os.getenv('CHANNEL')           # 签到目标频道名或 @username
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN') # 你的通知机器人 Token
TG_CHAT_ID = os.getenv('TG_CHAT_ID')     # 你的个人或群组 Chat ID

BOT_ID = 7694509436                        # @CloudCatOfficialBot 的用户 ID
CHECK_WAIT_TIME = 20                       # 等待机器人回复的时间（秒）
# ============================================

# 定义颜色和符号 (用于日志美化)
COLORS = {
    'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
    'blue': '\033[94m', 'magenta': '\033[95m', 'cyan': '\033[96m',
    'white': '\033[97m', 'reset': '\033[0m'
}
SYMBOLS = {'check': '✓', 'warning': '⚠', 'arrow': '➜', 'error': '✗'}

def log(color, symbol, message):
    """日志函数"""
    print(f"{COLORS[color]}{SYMBOLS[symbol]} {message}{COLORS['reset']}")

def send_tg_notification(status: str, message: str):
    """发送 Telegram 消息通知"""
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return

    emoji = "✅" if status == "成功" else "❌"
    notification_text = f"*CloudCat 签到任务通知*\n\n状态：{emoji} {status}\n频道：`{CHANNEL}`\n详情：{message}"
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
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
    if not all([API_ID, API_HASH, CHANNEL]):
        err_msg = "API_ID, API_HASH, 或 CHANNEL 环境变量未设置！请检查配置"
        log('red', 'error', err_msg)
        send_tg_notification("失败", err_msg)
        return

    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tg_session.session')
    
    log('cyan', 'arrow', "启动 Telegram 客户端并尝试以您的身份登录")
    
    try:
        async with TelegramClient(session_path, API_ID, API_HASH) as client:
            await client.start()
            
            # 1. 获取用户账户信息，并以此构造成功关键词
            me = await client.get_me()
            user_full_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            
            if not user_full_name:
                 # 确保即使名字全空，也有一个备用关键词
                 user_full_name = me.username or "yutian-青云志"
            
            SUCCESS_KEYWORD = user_full_name 
            log('cyan', 'arrow', f"检测到您的用户名为: '{SUCCESS_KEYWORD}'，将以此作为成功判断关键词")

            channel_entity = await client.get_entity(CHANNEL)
            log('cyan', 'arrow', f"已成功连接频道：{channel_entity.title}")

            # 发送签到命令 (单次签到)
            log('cyan', 'arrow', "发送签到命令 /checkin")
            sent_message = await client.send_message(channel_entity, '/checkin')
            log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒，寻找机器人回复")
            await asyncio.sleep(CHECK_WAIT_TIME)
            
            is_success = False
            check_limit = 5 # 检查最近5条消息

            # 遍历最新的消息
            async for msg in client.iter_messages(channel_entity, limit=check_limit):
                if isinstance(msg, Message) and msg.sender_id == BOT_ID:
                    
                    if msg.text and SUCCESS_KEYWORD in msg.text:
                        # 找到包含用户名的机器人回复，判定为成功
                        is_success = True
                        break

            if is_success:
                final_msg = f"签到成功！机器人（ID: {BOT_ID}）回复中包含您的用户名：'{SUCCESS_KEYWORD}'"
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
        log('yellow', 'warning', "请检查 API 配置、CHANNEL 名称是否正确，或尝试删除旧的 session 文件重新登录。")

if __name__ == '__main__':
    log('cyan', 'arrow', "开始执行频道签到任务...")
    asyncio.run(check_in())
    log('green', 'check', "任务结束。")
