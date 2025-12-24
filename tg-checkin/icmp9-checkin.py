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
        log('green', 'check', "TG 通知已发送")
    except Exception as e:
        log('red', 'error', f"TG 通知发送失败: {e}")

def parse_all_info(text: str, current_data: Dict[str, str]) -> Dict[str, str]:
    # 尝试匹配用户名
    user_match = re.search(r'📊\s*([^\n\r]+)', text)
    if user_match:
        name = user_match.group(1).split('━━')[0].strip()
        current_data['user'] = name
        log('green', 'check', f"解析到用户名: {name}")
    else:
        log('yellow', 'warning', "未匹配到用户名 (📊)")

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
        log('red', 'error', "消息中没有按钮可点击")
        return False
    
    coords = {
        '账户': (0, 1),
        '虚机': (0, 2)
    }

    if button_text in coords:
        row, col = coords[button_text]
        try:
            await msg.click(row, col)
            log('green', 'check', f"已执行坐标点击 Row:{row} Col:{col} ([{button_text}])")
            return True
        except Exception as e:
            log('yellow', 'warning', f"坐标点击尝试失败: {e}")

    # 模糊匹配备选
    for row in msg.buttons:
        for button in row:
            if button_text in button.button.text:
                await button.click()
                log('green', 'check', f"已通过模糊匹配发送点击: [{button.button.text}]")
                return True
    
    log('red', 'error', f"未找到名为 [{button_text}] 的按钮")
    return False

async def main():
    if not (TG_API_ID and TG_API_HASH):
        log('red', 'error', "环境变量缺失: 请检查 TG_API_ID 和 TG_API_HASH"); return

    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_session")
    info = {'status': '失败', 'gained': '0 GB', 'vm_info': '暂无数据'}
    client = TelegramClient(session_path, TG_API_ID, TG_API_HASH)

    try:
        log('cyan', 'arrow', "正在连接 Telegram 服务器...")
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "Session 已失效, 请重新生成 tg_session 文件"); return
        
        log('green', 'check', f"TG 登录成功, 目标机器人: {TARGET_BOT_USERNAME}")
        bot = await client.get_entity(TARGET_BOT_USERNAME)
        
        # 1. 签到
        log('cyan', 'arrow', f"发送签到指令 /checkin")
        await client.send_message(bot, '/checkin')
        log('cyan', 'arrow', "等待 5s 接收初始回复...")
        await asyncio.sleep(5)
        
        msgs = await client.get_messages(bot, limit=1)
        if not msgs: 
            log('red', 'error', "未能收到机器人回复, 任务终止")
            return
        msg_obj = msgs[0]
        
        log('cyan', 'arrow', f"收到消息内容预览: {msg_obj.text[:40].replace(chr(10), ' ')}...")
        info = parse_all_info(msg_obj.text, info)
        info['status'] = "✅ 签到成功" if "成功" in msg_obj.text else "ℹ️ 今日已签"

        # 2. 账户详情
        log('cyan', 'arrow', "准备获取账户配额信息...")
        if await safe_click(msg_obj, '账户'):
            log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME}s 让机器人刷新页面...")
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            
            # 容错：如果还是旧内容则加等 5s
            if "今日已经签到" in refreshed.text and "配额" not in refreshed.text:
                log('yellow', 'warning', "消息尚未刷新, 额外等待 5s...")
                await asyncio.sleep(5)
                refreshed = await client.get_messages(bot, ids=msg_obj.id)
            
            log('cyan', 'arrow', f"账户刷新内容快照: {refreshed.text[:50].replace(chr(10), ' ')}...")
            info = parse_all_info(refreshed.text, info)
            msg_obj = refreshed

        # 3. 虚机详情
        log('cyan', 'arrow', "准备获取虚拟机列表...")
        if await safe_click(msg_obj, '虚机'):
            log('cyan', 'arrow', f"等待 {CHECK_WAIT_TIME}s 抓取虚机列表...")
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            
            if refreshed and ("虚拟机" in refreshed.text or "没有虚拟机" in refreshed.text):
                log('green', 'check', "虚机内容抓取成功")
                parts = refreshed.text.split('━━━━━━━━━━━━━━')
                info['vm_info'] = parts[-1].strip() if len(parts) > 1 else refreshed.text
            else:
                log('yellow', 'warning', "未能捕获虚机详情文本，请检查快照内容")
                log('cyan', 'arrow', f"快照原文: {refreshed.text.replace(chr(10), ' ')}")

        # 4. 总结
        log('green', 'check', f"流程处理完毕. 用户: {info.get('user', '未知')}, 状态: {info.get('status')}")
        send_tg_notification(info)
        
    except Exception as e:
        log('red', 'error', f"程序运行发生严重错误: {str(e)}")
        traceback.print_exc()
    finally:
        await client.disconnect()
        log('cyan', 'arrow', "与 Telegram 连接已断开")

if __name__ == '__main__':
    log('cyan', 'arrow', "=== 开始执行 ICMP9 自动签到脚本 ===")
    asyncio.run(main())
