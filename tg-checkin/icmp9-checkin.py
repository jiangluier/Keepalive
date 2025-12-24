import os
import sys
import asyncio
import re
import requests
import io
from telethon import TelegramClient
from typing import Dict, Any

# 强制 UTF-8 编码，防止日志乱码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')      # 通知机器人 Token
TG_CHAT_ID = os.getenv('TG_CHAT_ID')          # 接收通知的个人 ID
TARGET_BOT_USERNAME = '@ICMP9_Bot'
TARGET_BOT_ID = 8595031564
CHECK_WAIT_TIME = 8                           # 点击按钮后的等待时间
# ============================================

COLORS = {'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m', 'cyan': '\033[96m', 'reset': '\033[0m'}
SYMBOLS = {'check': '✅', 'warning': '⚠️', 'arrow': '➜', 'error': '❌', 'info': '📊'}

def log(color: str, symbol_key: str, message: str):
    icon = SYMBOLS.get(symbol_key, symbol_key)
    print(f"{COLORS[color]}{icon} {message}{COLORS['reset']}")

def send_tg_notification(data: Dict[str, str]):
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置通知变量，跳过通知")
        return

    text = (
        f"🤖 *ICMP9 签到报告* 🤖\n"
        f"━━━━━━━━━━━━\n"
        f"👤 账户: {data.get('user', '未知')}\n"
        f"📅 状态: {data.get('status', '未知')}\n"
        f"🎁 今日已获: {data.get('gained', '0 GB')}\n"
        f"🔥 连续签到: {data.get('streak', '未知')}\n"
        f"━━━━━━━━━━━━\n"
        f"📦 总配额: {data.get('total', '未知')}\n"
        f"📈 已使用: {data.get('used', '未知')}\n"
        f"📉 剩余量: {data.get('remaining', '未知')}\n"
        f"🖥️ 虚机数: {data.get('vm_count', '未知')}\n"
        f"📝 虚机信息: {data.get('vm_info', '无')}"
    )
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}, timeout=15).raise_for_status()
    except Exception as e:
        log('red', 'error', f"发送通知失败: {e}")

def parse_all_info(text: str, current_data: Dict[str, str]) -> Dict[str, str]:
    log('cyan', 'info', f"正在解析文本：{len(text)}")
    
    user_match = re.search(r'📊\s*([^\n\r]+)', text)
    if user_match: current_data['user'] = user_match.group(1).strip()
    gained = re.search(r'(获得|今日已获)[：:]\s*(\+?[\d\.]+\s*[GMB]+)', text)
    if gained: current_data['gained'] = gained.group(2)
    streak = re.search(r'连续签到[：:]\s*(\d+\s*天)', text)
    if streak: current_data['streak'] = streak.group(1)
    quota = re.search(r'配额[：:]\s*([\d\.]+\s*[GMB]+)', text)
    if quota: current_data['total'] = quota.group(1)
    used = re.search(r'已用[：:]\s*([\d\.]+\s*[GMB]+)', text)
    if used: current_data['used'] = used.group(1)
    rem = re.search(r'剩余[：:]\s*([\d\.]+\s*[GMB]+)', text)
    if rem: current_data['remaining'] = rem.group(1)
    vms = re.search(r'虚机[：:]\s*(\d+)\s*台', text)
    if vms: current_data['vm_count'] = vms.group(1)
    
    return current_data

async def main():
    if not (TG_API_ID and TG_API_HASH):
        log('red', 'error', "环境变量缺失"); return

    session_name = 'tg_session'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    session_path = os.path.join(script_dir, f"{session_name}.session")
    
    if not os.path.exists(session_path):
        log('red', 'error', f"未找到 {session_path}"); return
    
    info = {'status': '失败', 'gained': '0 GB', 'vm_info': '暂无数据'}
    client = TelegramClient(os.path.join(script_dir, session_name), TG_API_ID, TG_API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "Session 失效"); return
        
        log('green', 'check', "登录成功，开始签到流程...")
        bot = await client.get_entity(TARGET_BOT_USERNAME)
        
        # 1. 签到
        await client.send_message(bot, '/checkin')
        await asyncio.sleep(CHECK_WAIT_TIME)
        
        # 2. 获取回复
        msgs = await client.get_messages(bot, limit=1)
        if not msgs: return
        msg_obj = msgs[0]
        info = parse_all_info(msg_obj.text, info)
        info['status'] = "✅ 签到成功" if "成功" in msg_obj.text else "ℹ️ 今日已签"

        # 3. 点击【账户】并强制刷新获取
        log('cyan', 'arrow', "点击 [账户] 按钮...")
        try:
            await msg_obj.click(text='账户')
            await asyncio.sleep(CHECK_WAIT_TIME)
            # 强制从服务器重新拉取该 ID 的消息，防止 Telethon 缓存
            refreshed_msgs = await client.get_messages(bot, ids=msg_obj.id)
            if refreshed_msgs:
                log('green', 'check', "已刷新账户文本")
                info = parse_all_info(refreshed_msgs.text, info)
        except Exception as e:
            log('yellow', 'warning', f"账户按钮操作失败: {e}")

        # 4. 点击【虚机】并强制刷新获取
        try:
            log('cyan', 'arrow', "点击 [虚机] 按钮...")
            await msg_obj.click(text='虚机')
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed_msgs = await client.get_messages(bot, ids=msg_obj.id)
            if refreshed_msgs and "虚拟机列表" in refreshed_msgs.text:
                parts = refreshed_msgs.text.split('━━━━━━━━━━━━━━')
                info['vm_info'] = parts[-1].strip() if len(parts) > 1 else refreshed_msgs.text
        except Exception as e:
            log('yellow', 'warning', f"虚机按钮操作失败: {e}")

        log('green', 'check', f"最终状态: {info['status']}")
        send_tg_notification(info)
    
    except Exception as e:
        log('red', 'error', f"发生异常: {e}")
    finally:
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
    
