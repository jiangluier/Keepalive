import os
import sys
import asyncio
import re
import requests
from telethon import TelegramClient, events
from telethon.tl.custom.message import Message
from typing import Dict, Any, Tuple

# Windows 事件循环兼容
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
TG_API_ID = os.getenv('TG_API_ID')
TG_API_HASH = os.getenv('TG_API_HASH')
TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')      # 通知机器人 Token
TG_CHAT_ID = os.getenv('TG_CHAT_ID')          # 接收通知的个人 ID
TARGET_BOT_USERNAME = '@ICMP9_Bot'            # 目标机器人
TARGET_BOT_ID = 8595031564                    # 目标机器人 ID
CHECK_WAIT_TIME = 5                           # 等待回复时间
# ============================================

COLORS = {'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m', 'cyan': '\033[96m', 'reset': '\033[0m'}
SYMBOLS = {'check': '✅', 'warning': '⚠️', 'arrow': '➜', 'error': '❌', 'info': '📊'}

def log(color: str, symbol: str, message: str):
    print(f"{COLORS[color]}{symbol} {message}{COLORS['reset']}")

def send_tg_notification(data: Dict[str, str]):
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log('yellow', 'warning', "未设置通知变量，跳过通知")
        return

    text = (
        f"🤖 *ICMP9 签到报告*\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 账户: {data.get('user', '未知')}\n"
        f"📅 状态: {data.get('status', '未知')}\n"
        f"🎁 今日已获: {data.get('gained', '0 GB')}\n"
        f"🔥 连续签到: {data.get('streak', '未知')}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📦 总配额: {data.get('total', '未知')}\n"
        f"📈 已使用: {data.get('used', '未知')}\n"
        f"📉 剩余量: {data.get('remaining', '未知')}\n"
        f"🖥️ 虚机数: {data.get('vm_count', '未知')}\n"
        f"📝 虚机信息: {data.get('vm_info', '无')}"
    )
    
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
    except Exception as e:
        log('red', 'error', f"发送通知失败: {e}")

def parse_all_info(text: str, current_data: Dict[str, str]) -> Dict[str, str]:
    """解析签到回复和账户回复中的所有字段"""
    # 提取今日获得/配额/连续签到 (针对签到回复)
    gained = re.search(r'(获得|今日已获)：\+?([\d\.]+ \w+)', text)
    quota = re.search(r'(配额|当前配额)：([\d\.]+ \w+)', text)
    streak = re.search(r'连续签到：(\d+ 天)', text)
    
    # 提取详细账户信息 (针对账户按钮回复)
    user = re.search(r'📊 (.*)', text)
    used = re.search(r'已用：([\d\.]+ \w+)', text)
    rem = re.search(r'剩余：([\d\.]+ \w+)', text)
    vms = re.search(r'虚机：(\d+) 台', text)

    if gained: current_data['gained'] = gained.group(2)
    if quota: current_data['total'] = quota.group(2)
    if streak: current_data['streak'] = streak.group(1)
    if user: current_data['user'] = user.group(1).strip()
    if used: current_data['used'] = used.group(1)
    if rem: current_data['remaining'] = rem.group(1)
    if vms: current_data['vm_count'] = vms.group(1)
    
    return current_data

async def main():
    if not (TG_API_ID and TG_API_HASH):
        log('red', 'error', "环境变量缺失"); return

    session_name = 'tg_session'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    session_path = os.path.join(script_dir, f"{session_name}.session")
    session_path_no_ext = os.path.join(script_dir, session_name)
    if not os.path.exists(session_path):
        log('red', 'error', f"错误: 未找到 {session_path} 文件！")
        return # 提前退出
    
    info = {'status': '失败', 'gained': '0 GB', 'vm_info': '暂无数据'}
    client = TelegramClient(session_path_no_ext, TG_API_ID, TG_API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log('red', 'error', "tg-session 已失效或未登录，请在重新生成后上传")
            return
        log('green', 'check', "tg-session 验证成功, 正在执行任务...")
        
        bot = await client.get_entity(TARGET_BOT_USERNAME)
        
        # 1. 发送签到命令
        log('cyan', 'arrow', "发送 /checkin")
        await client.send_message(bot, '/checkin')
        await asyncio.sleep(CHECK_WAIT_TIME)
        
        # 2. 获取回复并解析
        msgs = await client.get_messages(bot, limit=1)
        if not msgs: return
        
        reply_text = msgs[0].text
        info = parse_all_info(reply_text, info)
        
        if "签到成功" in reply_text:
            info['status'] = "✅ 签到成功"
        elif "已经签到" in reply_text:
            info['status'] = "ℹ️ 今日已签"
        
        # 3. 点击“账户”按钮以获取更详细的数据
        log('cyan', 'arrow', "点击 [账户] 按钮获取详情...")
        try:
            # 查找名为 "账户" 的按钮并点击
            await msgs[0].click(text='账户')
            await asyncio.sleep(CHECK_WAIT_TIME)
            # 获取点击按钮后的新回复
            acc_msgs = await client.get_messages(bot, limit=1)
            info = parse_all_info(acc_msgs[0].text, info)
        except Exception as e:
            log('yellow', 'warning', f"点击按钮失败: {e}")

        # 4. 点击“虚机”按钮获取虚机详情
        try:
            await msgs[0].click(text='虚机')
            await asyncio.sleep(CHECK_WAIT_TIME)
            vm_msgs = await client.get_messages(bot, limit=1)
            if "虚拟机列表" in vm_msgs[0].text:
                info['vm_info'] = vm_msgs[0].text.split('━━━━━━━━━━━━━━')[-1].strip()
        except:
            pass

        log('green', 'check', f"任务完成: {info['status']}")
        send_tg_notification(info)
    
    except Exception as e:
        log('red', 'error', f"运行中出错: {e}")
    finally:
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
