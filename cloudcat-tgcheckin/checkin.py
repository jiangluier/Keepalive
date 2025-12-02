import os
import sys
import asyncio
from telethon import TelegramClient

# Windows 事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ================= 配置区域 =================
# 必须设置的环境变量
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
CHANNEL = os.getenv('CHANNEL') # 签到目标频道名或 @username
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

async def check_in():
    """仅执行频道签到操作的主逻辑"""
    
    # 检查必要的环境变量
    if not all([API_ID, API_HASH, CHANNEL]):
        log('red', 'error', "API_ID, API_HASH, 或 CHANNEL 环境变量未设置！请检查配置。")
        return

    # 会话文件路径（用于保存登录状态）
    session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tg_session.session')
    
    log('cyan', 'arrow', "启动 Telegram 客户端并尝试连接...")
    
    try:
        # 使用 with 块管理客户端连接
        async with TelegramClient(session_path, API_ID, API_HASH) as client:
            # 确保客户端已启动并登录
            await client.start()
            
            # 获取频道实体
            channel_entity = await client.get_entity(CHANNEL)
            log('cyan', 'arrow', f"已连接频道：{channel_entity.title}")
            
            # 发送签到消息
            log('cyan', 'arrow', "发送签到命令 /checkin ...")
            await client.send_message(channel_entity, '/checkin')
            
            log('green', 'check', "签到命令 /checkin 已成功发送！")

    except Exception as e:
        # 捕获并记录所有连接或发送错误
        log('red', 'error', f"签到失败: {type(e).__name__} - {str(e)}")
        log('yellow', 'warning', "请检查 API 配置、CHANNEL 名称是否正确，或尝试手动登录以创建 session 文件。")

if __name__ == '__main__':
    log('cyan', 'arrow', "开始执行频道签到任务...")
    asyncio.run(check_in())
    log('green', 'check', "任务完成！")
