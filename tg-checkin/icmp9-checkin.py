import os
import sys
import asyncio
import re
import requests
import traceback
from telethon import TelegramClient
from typing import Dict, Any

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
TARGET_BOT_USERNAME = '@ICMP9_Bot'
CHECK_WAIT_TIME = 10
# ============================================

COLORS = {'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m', 'cyan': '\033[96m', 'reset': '\033[0m'}
SYMBOLS = {'check': '✅', 'warning': '⚠️', 'arrow': '➡️', 'error': '❌'}

def log(color_key: str, symbol_key: str, message: str):
    color = COLORS.get(color_key, COLORS['reset'])
    icon = SYMBOLS.get(symbol_key, symbol_key)
    print(f"{color}{icon} {message}{COLORS['reset']}")

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
        f"📝 虚机详情: {data.get('vm_info', '无')}"
    )
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}, timeout=15).raise_for_status()
        log('green', 'check', "通知发送成功")
    except Exception as e:
        log('red', 'error', f"通知发送失败: {e}")

def parse_all_info(text: str, current_data: Dict[str, str]) -> Dict[str, str]:
    user_match = re.search(r'📊\s*([^\n\r]+)', text)
    if user_match:
        name = user_match.group(1).split('━━')[0].strip()
        current_data['user'] = name

    gained = re.search(r'今日已获[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if gained: current_data['gained'] = gained.group(1)
    
    streak = re.search(r'连续签到[：:\s]+(\d+)', text)
    if streak: current_data['streak'] = f"{streak.group(1)} 天"
    
    quota = re.search(r'配额[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if quota: current_data['total'] = quota.group(1)
    
    used = re.search(r'已用[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if used: current_data['used'] = used.group(1)
    
    rem = re.search(r'剩余[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if rem: current_data['remaining'] = rem.group(1)
    
    vms = re.search(r'虚机[：:\s]+(\d+)\s*台', text)
    if vms: current_data['vm_count'] = vms.group(1)
    
    return current_data

async def safe_click(msg, button_text):
    log('cyan', 'arrow', f"尝试点击按钮: [{button_text}]")
    if not msg or not msg.buttons:
        log('red', 'error', "消息中没有按钮")
        return False
    
    try:
        await msg.click(text=button_text)
        log('green', 'check', f"已通过文本匹配发送点击: {button_text}")
        return True
    except:
        for row in msg.buttons:
            for button in row:
                if button_text in button.button.text:
                    await button.click()
                    log('green', 'check', f"已通过模糊匹配发送点击: {button.button.text}")
                    return True
    return False

async def main():
    if not (TG_API_ID and TG_API_HASH):
        log('red', 'error', "环境变量缺失"); return

    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_session")
    info = {'status': '失败', 'gained': '0 GB', 'vm_info': '暂无数据'}
    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "Session 已失效"); return
        
        log('green', 'check', "TG 登录成功")
        bot = await client.get_entity(TARGET_BOT_USERNAME)
        
        # 1. 签到
        await client.send_message(bot, '/checkin')
        await asyncio.sleep(5)
        
        msgs = await client.get_messages(bot, limit=1)
        if not msgs: return
        msg_obj = msgs[0]
        
        info = parse_all_info(msg_obj.text, info)
        info['status'] = "✅ 签到成功" if "成功" in msg_obj.text else "ℹ️ 今日已签"

        # 2. 账户详情
        log('cyan', 'arrow', "正在请求账户详情...")
        if await safe_click(msg_obj, '账户'):
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            # 如果刷新后还是旧内容，多等一下再拉取一次
            if "今日已经签到" in refreshed.text:
                await asyncio.sleep(5)
                refreshed = await client.get_messages(bot, ids=msg_obj.id)
            
            log('cyan', 'arrow', f"账户内容快照: {refreshed.text[:30].replace(chr(10), ' ')}...")
            info = parse_all_info(refreshed.text, info)
            msg_obj = refreshed

        # 3. 虚机详情
        log('cyan', 'arrow', "正在请求虚机详情...")
        if await safe_click(msg_obj, '虚机'):
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            # 容错：只要有“虚拟机”或“当前没有”字样就解析
            if refreshed and ("虚拟机" in refreshed.text or "没有虚拟机" in refreshed.text):
                log('green', 'check', "虚机内容抓取成功")
                parts = refreshed.text.split('━━━━━━━━━━━━━━')
                info['vm_info'] = parts[-1].strip() if len(parts) > 1 else refreshed.text
            else:
                log('yellow', 'warning', "未检测到虚机列表文本")

        log('green', 'check', f"任务结束, 账户: {info.get('user')}")
        send_tg_notification(info)
        
    except Exception as e:
        log('red', 'error', f"程序崩溃: {str(e)}")
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == '__main__':
    log('cyan', 'arrow', "=== 开始执行 ICMP9 自动签到脚本 ===")
    asyncio.run(main())
