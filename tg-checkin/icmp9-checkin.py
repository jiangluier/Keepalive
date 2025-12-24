import os
import sys
import asyncio
import re
import requests
import io
import traceback
from telethon import TelegramClient
from typing import Dict, Any

# ================= 运行环境兼容 =================
# 强制 UTF-8 编码，确保 GitHub Actions 日志中的 Emoji 正常显示
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
CHECK_WAIT_TIME = 8                           # 增加等待时间，确保 Bot 响应
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
        log('green', 'check', "通知发送成功")
    except Exception as e:
        log('red', 'error', f"通知发送失败: {e}")

def parse_all_info(text: str, current_data: Dict[str, str]) -> Dict[str, str]:
    """正则解析消息文本"""
    user_match = re.search(r'📊\s*([^━━━━━━━━\n\r]+)', text)
    if user_match: current_data['user'] = user_match.group(1).strip()
    
    gained = re.search(r'(获得|今日已获)[：:\s]+(\+?[\d\.]+\s*[GMB]+)', text)
    if gained: current_data['gained'] = gained.group(2)
    
    streak = re.search(r'连续签到[：:\s]+(\d+\s*天)', text)
    if streak: current_data['streak'] = streak.group(1)
    
    quota = re.search(r'(配额|总配额|当前配额)[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if quota: current_data['total'] = quota.group(2)
    
    used = re.search(r'已用[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if used: current_data['used'] = used.group(1)
    
    rem = re.search(r'剩余[：:\s]+([\d\.]+\s*[GMB]+)', text)
    if rem: current_data['remaining'] = rem.group(1)
    
    vms = re.search(r'虚机[：:\s]+(\d+)\s*台', text)
    if vms: current_data['vm_count'] = vms.group(1)
    
    return current_data

async def safe_click(msg, button_text):
    """多策略点击按钮"""
    log('cyan', 'arrow', f"尝试点击按钮: [{button_text}]")
    if not msg.buttons:
        log('red', 'error', "该消息没有任何按钮")
        return False
    
    # 策略1: 文本直接匹配
    try:
        await msg.click(text=button_text)
        log('green', 'check', f"已通过文本匹配发送点击: {button_text}")
        return True
    except:
        pass
    
    # 策略2: 模糊遍历匹配
    for row in msg.buttons:
        for button in row:
            if button_text in button.button.text:
                await button.click()
                log('green', 'check', f"已通过模糊匹配发送点击: {button.button.text}")
                return True
    
    log('red', 'error', f"未找到名为 [{button_text}] 的按钮")
    return False

async def main():
    if not (TG_API_ID and TG_API_HASH):
        log('red', 'error', "环境变量缺失: TG_API_ID 或 TG_API_HASH"); return

    session_name = 'tg_session'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    session_path = os.path.join(script_dir, f"{session_name}.session")
    
    if not os.path.exists(session_path):
        log('red', 'error', f"未找到 Session 文件: {session_path}"); return
    
    info = {'status': '失败', 'gained': '0 GB', 'vm_info': '暂无数据'}
    client = TelegramClient(os.path.join(script_dir, session_name), TG_API_ID, TG_API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "Session 已失效，请在本地重新登录生成"); return
        
        log('green', 'check', "TG 登录成功，正在获取机器人实体...")
        bot = await client.get_entity(TARGET_BOT_USERNAME)
        
        # --- 步骤1: 签到 ---
        log('cyan', 'arrow', "发送签到命令 /checkin")
        await client.send_message(bot, '/checkin')
        await asyncio.sleep(CHECK_WAIT_TIME)
        
        msgs = await client.get_messages(bot, limit=1)
        if not msgs:
            log('red', 'error', "未收到初始回复"); return
        
        msg_obj = msgs[0]
        log('info', 'info', f"初始消息预览: {msg_obj.text.replace(chr(10), ' ')[:50]}...")
        
        info = parse_all_info(msg_obj.text, info)
        info['status'] = "✅ 签到成功" if "成功" in msg_obj.text else "ℹ️ 今日已签"

        # --- 步骤2: 账户详情 ---
        log('cyan', 'arrow', "正在处理账户详情...")
        if await safe_click(msg_obj, '账户'):
            await asyncio.sleep(CHECK_WAIT_TIME)
            # 强制通过 ID 获取最新编辑的内容
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            if refreshed:
                log('info', 'info', f"账户刷新后预览: {refreshed.text.replace(chr(10), ' ')[:50]}...")
                info = parse_all_info(refreshed.text, info)
                msg_obj = refreshed # 更新消息对象用于下一步
        
        # --- 步骤3: 虚机详情 ---
        log('cyan', 'arrow', "正在处理虚机详情...")
        if await safe_click(msg_obj, '虚机'):
            await asyncio.sleep(CHECK_WAIT_TIME)
            refreshed = await client.get_messages(bot, ids=msg_obj.id)
            if refreshed and "虚拟机列表" in refreshed.text:
                log('green', 'check', "已捕获虚机列表内容")
                parts = refreshed.text.split('━━━━━━━━━━━━━━')
                info['vm_info'] = parts[-1].strip() if len(parts) > 1 else refreshed.text
            else:
                log('yellow', 'warning', "未能获取到虚机列表文本")

        # --- 步骤4: 总结与通知 ---
        log('green', 'check', f"签到任务结束。账户: {info.get('user')}, 状态: {info.get('status')}")
        send_tg_notification(info)
        
    except Exception as e:
        log('red', 'error', f"程序运行奔溃: {str(e)}")
        traceback.print_exc()
    finally:
        await client.disconnect()

if __name__ == '__main__':
    log('cyan', 'info', "=== 开始执行 ICMP9 签到自动化脚本 ===")
    asyncio.run(main())
