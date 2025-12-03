import os
import sys
import asyncio
import requests
from telethon import TelegramClient
from telethon.tl.custom.message import Message
from typing import Dict, Any, Tuple
import re

# Windows事件循环策略，兼容win系统运行
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')      # 你的通知机器人 Token
TG_CHAT_ID = os.getenv('TG_CHAT_ID')          # 你的个人 Chat ID (接收通知用)
TARGET_BOT_USERNAME = '@EmbyPublicBot'        # 签到目标机器人用户名
TARGET_BOT_ID = 1429576125                    # 签到目标机器人 ID
CHECK_WAIT_TIME = 5                           # 等待机器人回复的时间（秒）
DEFAULT_GAINED_POINTS = "已签"                 # 获得积分的默认值
DEFAULT_TOTAL_POINTS = "未知"                  # 总积分的默认值
# ============================================

# 定义颜色和符号 (用于日志美化)
COLORS: Dict[str, str] = {
    'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
    'cyan': '\033[96m', 'reset': '\033[0m'
}
SYMBOLS: Dict[str, str] = {'check': '✓', 'warning': '⚠', 'arrow': '➜', 'error': '✗'}

# 日志函数
def log(color: str, symbol: str, message: str):
    print(f"{COLORS[color]}{SYMBOLS[symbol]} {message}{COLORS['reset']}")

# 发送 Telegram 消息通知模板
def send_tg_notification(status: str, gained: str, total: str):
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过通知")
        return

    
    target_bot_link = TARGET_BOT_USERNAME.replace('@', 't.me/') if TARGET_BOT_USERNAME.startswith('@') else TARGET_BOT_USERNAME # 构造链接
    status_emoji = "✅" if status == "成功" else ("⭐" if status == "今日已签到" else "❌")
    notification_text = (
        f"🤖 *Auto SheerID 签到通知* 🤖\n"
        f"====================\n"
        f"{status_emoji} 状态: {status}\n"
        f"🎯 目标: [{TARGET_BOT_USERNAME}]({target_bot_link})\n"
        f"📌 今日获得: {gained}\n"
        f"📊 当前总分: {total}"
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

# 解析积分信息 (适用于 Emby Bot)
def parse_emby_points(message_text: str) -> Tuple[str, str]:
    """从 Emby Bot 消息文本中解析 '获得积分' 和 '当前积分'"""
    gained_points = DEFAULT_GAINED_POINTS
    total_points = DEFAULT_TOTAL_POINTS
    gained_match = re.search(r'获得了\s*(\d+)\s*积分', message_text)
    total_match = re.search(r'总分[:：]\s*(\d+)', message_text)

    if gained_match:
        gained_points = f"{gained_match.group(1)}分"   
    if total_match:
        total_points = f"{total_match.group(1)}分"

    return gained_points, total_points

# 等待并获取目标机器人最新回复
async def get_bot_reply(client: TelegramClient, peer_entity: Any, check_limit: int = 10) -> Message | None:
    log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME} 秒后读取机器人回复")
    await asyncio.sleep(CHECK_WAIT_TIME)
    
    # 在私聊中，peer_entity 就是机器人本身
    async for msg in client.iter_messages(peer_entity, limit=check_limit):
        if isinstance(msg, Message) and msg.sender_id == TARGET_BOT_ID:
            return msg
    
    return None

# 执行签到主逻辑
async def check_in_emby():
    # 检查核心登录变量
    if not (TG_API_ID and TG_API_HASH):
        log('red', 'error', "缺少 TG_API_ID 或 TG_API_HASH，请检查环境变量设置")
        sys.exit(1)

    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tg_session.session')
    
    status = "失败"
    gained_points = DEFAULT_GAINED_POINTS
    total_points = DEFAULT_TOTAL_POINTS
    BUTTON_ATTEMPTS = 3  # 按钮索引，从 0 开始
    
    try:
        async with TelegramClient(session_path, TG_API_ID, TG_API_HASH) as client:
            await client.start()
            
            try:
                bot_entity = await client.get_entity(TARGET_BOT_USERNAME)
                log('cyan', 'arrow', f"已连接到机器人: {TARGET_BOT_USERNAME}")
            except Exception as e:
                log('red', 'error', f"无法找到机器人 {TARGET_BOT_USERNAME}: {e}")
                return

            log('cyan', 'arrow', "发送 /checkin 签到命令")
            await client.send_message(bot_entity, '/checkin')
            initial_reply = await get_bot_reply(client, bot_entity, CHECK_WAIT_TIME)
            
            if not initial_reply or not initial_reply.text:
                 log('red', 'error', "未收到 /checkin 后的机器人回复")
                 # 尝试直接解析回复，因为可能直接回复“已签到”而没有按钮
                 status = "未知响应"
                 if initial_reply and ('已签到' in initial_reply.text or '机会已用完' in initial_reply.text):
                     status = "今日已签到"
                     gained_points, total_points = parse_emby_points(initial_reply.text)
                 else:
                     log('red', 'error', "无法识别机器人的回复内容")
            
            # 情况 B: 今日已签到 (在有按钮回复前处理)
            elif '已签到' in initial_reply.text or '机会已用完' in initial_reply.text:
                status = "今日已签到"
                log('yellow', 'warning', "判断为：今日已签到")
                gained_points, total_points = parse_emby_points(initial_reply.text)
                
            # 情况 C: 首次签到，需要点击按钮
            elif initial_reply.buttons:
                log('yellow', 'warning', "判断为：需要图片验证码，开始尝试点击按钮")
                if not initial_reply.buttons[0]:
                    log('red', 'error', "机器人回复中未检测到按钮")
                    return
                
                buttons = initial_reply.buttons[0]
                for i in range(min(len(buttons), BUTTON_ATTEMPTS)):
                    button_label = buttons[i].text
                    log('cyan', 'arrow', f"尝试点击第 {i+1} 个按钮: {button_label}")
                    click_reply = await initial_reply.click(i)  # 点击按钮并等待回复
                    action_reply = await get_bot_reply(client, bot_entity, EMBY_CHECK_WAIT_TIME)  # 点击后，最新的回复将是下一条消息
                    
                    if action_reply and action_reply.text:
                        reply_text = action_reply.text
                        log('green', 'check', f"收到回复:\n{reply_text}")
                        
                        # 成功判断
                        if '签到成功' in reply_text:
                            status = "成功"
                            log('green', 'check', "判断为：签到成功")
                            gained_points, total_points = parse_emby_points(reply_text)
                            break # 成功，跳出循环
                        
                        # 错误判断
                        elif '错误' in reply_text:
                            log('yellow', 'warning', f"点击 {button_label} 错误，继续尝试下一个")
                        
                        else:
                            status = "未知响应"
                            log('red', 'error', "无法识别点击后的回复内容")
                            break # 未知错误，停止尝试
                    else:
                        log('red', 'error', "点击按钮后未收到回复")
                        break # 未收到回复，停止尝试
                
                # 检查是否成功
                if status != "成功" and status != "今日已签到":
                    status = "按钮尝试失败"
                    log('red', 'error', f"已尝试 {BUTTON_ATTEMPTS} 个按钮，签到失败"

            else:
                status = "未知响应"
                log('red', 'error', "无法识别机器人的回复内容或未找到按钮")

    except Exception as e:
        log('red', 'error', f"脚本执行出错: {e}")
        sys.exit(1)

    # === 最终通知 ===
    log('cyan', 'arrow', f"执行结束 - 状态: {status}, 获得: {gained_points}, 总分: {total_points}")
    send_tg_notification(status, gained_points, total_points)

# 主执行块
if __name__ == '__main__':
    log('cyan', 'arrow', f"=== 执行 {EMBY_BOT_USERNAME} 签到任务 ===")
    asyncio.run(check_in_emby())
