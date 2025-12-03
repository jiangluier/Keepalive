import os
import sys
import asyncio
import requests
from telethon import TelegramClient
from telethon.tl.custom.message import Message
from typing import Dict, Any, Tuple
import re

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
CHECK_WAIT_TIME = 10                     # 等待机器人回复的时间（秒）
# ============================================

# 定义颜色和符号 (用于日志美化)
COLORS: Dict[str, str] = {
    'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
    'cyan': '\033[96m', 'reset': '\033[0m'
}
SYMBOLS: Dict[str, str] = {'check': '✓', 'warning': '⚠', 'arrow': '➜', 'error': '✗'}

def log(color: str, symbol: str, message: str):
    """日志函数"""
    print(f"{COLORS[color]}{SYMBOLS[symbol]} {message}{COLORS['reset']}")

def send_tg_notification(status: str, gained: str, total: str):
    """发送 Telegram 消息通知 (使用新模板)"""
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return

    # 构造可点击的频道链接
    channel_link = TG_CHANNEL.replace('@', 't.me/') if TG_CHANNEL.startswith('@') else TG_CHANNEL
    
    # 状态 Emoji
    status_emoji = "✅" if status == "成功" else ("⭐" if status == "今日已签到" else "❌")

    notification_text = (
        f"🎉 TG 签到任务通知 🎉\n"
        f"====================\n"
        f"🔔 状态：{status_emoji} {status}\n"
        f"📢 频道：[{TG_CHANNEL}]({channel_link})\n"
        f"======== 详情 ========\n"
        f"⭐ 今日签到积分: {gained}\n"
        f"⭐ 您的总积分: {total}"
    )
    
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

def parse_points_from_message(message_text: str, is_points_command_reply: bool) -> Tuple[str, str]:
    """根据消息类型解析本次签到积分和总积分"""
    gained_points = "0⭐"
    total_points = "未知⭐"
    
    if is_points_command_reply:
        # 解析今日签到积分
        gained_match = re.search(r'CheckInAddPoint:\s*(\d+\.?\d*)\s?⭐', message_text, re.IGNORECASE)
        # 解析总积分（/points 命令回复中总积分后面没有⭐）
        total_match = re.search(r'(?:当前积分[:：]|current points[:：]\s*)(\d+\.?\d*)', message_text, re.IGNORECASE)
    else:
        # 解析签到获得的积分
        gained_match = re.search(r'(?:获得|you got)\s*(\d+\.?\d*)\s?⭐', message_text, re.IGNORECASE)
        # 解析总积分（/checkin 命令回复中总积分后面有⭐）
        total_match = re.search(r'(?:当前积分[:：]|current points:\s*)(\d+\.?\d*)\s?⭐', message_text, re.IGNORECASE)

    if gained_match:
        gained_points = f"{gained_match.group(1)}⭐"
    
    if total_match:
        try:
            total_score = float(total_match.group(1))
            total_points = f"{int(total_score)}⭐"  # 转换为整数并添加⭐
        except ValueError:
            pass

    return gained_points, total_points


async def get_bot_reply(client: TelegramClient, channel_entity: Any, check_limit: int) -> Message | None:
    """等待并获取目标机器人最新的回复消息"""
    log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒后开始查找机器人回复...")
    await asyncio.sleep(CHECK_WAIT_TIME)
    
    log('cyan', 'arrow', f"开始查找最近 {check_limit} 条消息...")
    message_count = 0
    
    async for msg in client.iter_messages(channel_entity, limit=check_limit):
        message_count += 1
        if isinstance(msg, Message):
            # 显示消息详情用于调试
            sender_info = f"Sender ID: {msg.sender_id}"
            text_preview = (msg.text[:50] + '...') if msg.text and len(msg.text) > 50 else (msg.text or '[无文本]')
            log('cyan', 'arrow', f"消息 #{message_count}: {sender_info} | 内容: {text_preview}")
            
            if msg.sender_id == CHANNEL_BOT_ID:
                log('green', 'check', f"✓ 找到目标机器人 (ID: {CHANNEL_BOT_ID}) 的回复！")
                return msg
    
    log('yellow', 'warning', f"在最近 {message_count} 条消息中未找到目标机器人 (ID: {CHANNEL_BOT_ID}) 的回复")
    return None

async def check_in():
    """执行频道签到并判断结果的主逻辑"""
    
    # 检查核心登录变量
    required_vars = {'TG_API_ID': TG_API_ID, 'TG_API_HASH': TG_API_HASH}
    missing_vars = [name for name, val in required_vars.items() if not val]
    
    if missing_vars:
        err_msg = f"TG 登录失败：缺少必要的变量: {', '.join(missing_vars)}！请检查 GitHub Secrets 设置"
        log('red', 'error', err_msg)
        sys.exit(1)

    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tg_session.session')
    
    log('cyan', 'arrow', "启动 TG 并尝试登录")
    status = "失败"
    gained_points = "0⭐"
    total_points = "未知⭐"
    check_limit = 15  # 增加消息查找范围
    
    try:
        async with TelegramClient(session_path, TG_API_ID, TG_API_HASH) as client:
            await client.start()
            
            SUCCESS_KEYWORD = TG_NAME
            log('cyan', 'arrow', f"成功判断关键词设置为: '{SUCCESS_KEYWORD}'")

            channel_entity = await client.get_entity(TG_CHANNEL)
            log('cyan', 'arrow', f"已成功连接频道：{channel_entity.title}")

            # 先发送 /points 检查是否已签到
            log('cyan', 'arrow', "发送 /points 命令检查签到状态")
            await client.send_message(channel_entity, '/points')
            
            points_reply = await get_bot_reply(client, channel_entity, check_limit)

            if points_reply and points_reply.text:
                reply_text = points_reply.text
                log('green', 'check', f"收到 /points 回复，完整内容:\n{reply_text}")
                is_nickname_match = SUCCESS_KEYWORD in reply_text
                
                if is_nickname_match:
                    # 检查是否有今日签到记录（CheckInAddPoint）
                    if 'CheckInAddPoint:' in reply_text or 'CheckInAddPoint：' in reply_text:
                        # 今日已签到
                        status = "今日已签到"
                        log('green', 'check', "判断为：今日已签到（从 /points 回复中检测到 CheckInAddPoint）")
                        gained_points, total_points = parse_points_from_message(reply_text, True)
                    else:
                        # 今日未签到，需要发送 /checkin
                        log('cyan', 'arrow', "今日未签到，发送签到命令 /checkin")
                        await client.send_message(channel_entity, '/checkin')
                        
                        checkin_reply = await get_bot_reply(client, channel_entity, check_limit)
                        
                        if checkin_reply and checkin_reply.text:
                            checkin_text = checkin_reply.text
                            log('green', 'check', f"收到 /checkin 回复，完整内容:\n{checkin_text}")
                            checkin_nickname_match = SUCCESS_KEYWORD in checkin_text
                            
                            # 检查是否签到成功
                            if checkin_nickname_match and ('成功' in checkin_text or 'successful' in checkin_text):
                                status = "成功"
                                log('green', 'check', "判断为：签到成功")
                                gained_points, total_points = parse_points_from_message(checkin_text, False)
                            # 检查是否已经签到过了
                            elif '已签到' in checkin_text or 'already checked in' in checkin_text:
                                status = "今日已签到"
                                log('yellow', 'warning', "判断为：今日已签到（从 /checkin 回复中检测到）")
                                # 从之前的 /points 回复中获取积分
                                gained_points, total_points = parse_points_from_message(reply_text, True)
                            else:
                                status = "失败"
                                log('red', 'error', "未找到预期的签到成功或已签到关键词")
                        else:
                            status = "失败"
                            log('red', 'error', "发送 /checkin 后未收到机器人回复")
                else:
                    status = "失败"
                    log('red', 'error', f"/points 回复中未找到昵称 '{SUCCESS_KEYWORD}'")
            else:
                status = "失败"
                log('red', 'error', "发送 /points 后未收到目标机器人的回复")

    except Exception as e:
        err_msg = f"连接或执行过程中出现严重错误: {type(e).__name__} - {str(e)}"
        log('red', 'error', err_msg)
        log('yellow', 'warning', "请检查 API 配置、频道名称是否正确，或 Session 文件是否有效")
        sys.exit(1)

    # === 最终通知 ===
    log('cyan', 'arrow', f"最终结果 - 状态: {status}, 今日积分: {gained_points}, 总积分: {total_points}")
    
    if status == "失败":
        final_msg = "签到失败或无法确认。请查看日志获取详细错误。"
        log('red', 'error', final_msg)
        send_tg_notification(status, gained_points, total_points)
    else:
        send_tg_notification(status, gained_points, total_points)
        
    log('green', 'check', "任务结束")

if __name__ == '__main__':
    log('cyan', 'arrow', "开始执行频道签到任务")
    asyncio.run(check_in())
