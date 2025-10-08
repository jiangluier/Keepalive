#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于预设token/cookie的签到脚本，适用于服务器环境，无需浏览器

使用方式：
python3 checkin_token.py [options]

Options:
  --config FILE    指定配置文件路径
  --debug          启用调试模式
  --notify         启用通知推送
  --no-notify      禁用通知推送
"""

import json
import time
import sys
import logging
import argparse
import requests
from datetime import datetime

class LeafLowTokenCheckin:
    def __init__(self, config_file="config.accounts.json"):
        """初始化Token签到类"""
        self.config_file = config_file
        self.config = self.load_config()
        self.setup_logging()
        self.checkin_url = "https://checkin.leaflow.net"
        self.main_site = "https://leaflow.net"
        
    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"配置文件 {self.config_file} 未找到")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"配置文件 {self.config_file} 格式错误")
            sys.exit(1)
    
    def setup_logging(self):
        """设置日志"""
        log_level = getattr(logging, self.config['settings'].get('log_level', 'INFO').upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('leaflow_token_checkin.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_session(self, token_data):
        """根据token数据创建会话"""
        session = requests.Session()
        
        # 设置基本headers
        session.headers.update({
            'User-Agent': self.config['settings']['user_agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # 添加认证信息
        if 'cookies' in token_data:
            # 设置cookies
            for name, value in token_data['cookies'].items():
                session.cookies.set(name, value)
                
        if 'headers' in token_data:
            # 设置自定义headers (如Authorization)
            session.headers.update(token_data['headers'])
        
        return session
    
    def test_authentication(self, session, account_name):
        """测试认证是否有效"""
        try:
            # 尝试访问需要认证的页面
            test_urls = [
                f"{self.main_site}/dashboard",
                f"{self.main_site}/profile",
                f"{self.main_site}/user",
                self.checkin_url,
            ]
            
            for url in test_urls:
                response = session.get(url, timeout=30)
                self.logger.debug(f"[{account_name}] Test {url}: {response.status_code}")
                
                if response.status_code == 200:
                    content = response.text.lower()
                    if any(indicator in content for indicator in ['dashboard', 'profile', 'user', 'logout', 'welcome']):
                        self.logger.info(f"✅ 账户 [{account_name}] 身份验证有效")
                        return True, "身份验证成功"
                elif response.status_code in [301, 302, 303]:
                    location = response.headers.get('location', '')
                    if 'login' not in location.lower():
                        self.logger.info(f"✅ 账户 [{account_name}] 身份验证有效（重定向）")
                        return True, "身份验证成功（重定向）"
            
            return False, "身份验证失败-未找到有效的经过身份验证的页面"
            
        except Exception as e:
            return False, f"身份认证测试错误: {str(e)}"
    
    def perform_checkin(self, session, account_name):
        """执行签到操作"""
        self.logger.info(f"🎯 账户 [{account_name}] 正在执行签到...")
        
        try:
            # 方法1: 直接访问签到页面
            response = session.get(self.checkin_url, timeout=30)
            
            if response.status_code == 200:
                result = self.analyze_and_checkin(session, response.text, self.checkin_url, account_name)
                if result[0]:
                    return result
            
            # 方法2: 尝试API端点
            api_endpoints = [
                f"{self.checkin_url}/api/checkin",
                f"{self.checkin_url}/checkin",
                f"{self.main_site}/api/checkin",
                f"{self.main_site}/checkin"
            ]
            
            for endpoint in api_endpoints:
                try:
                    # GET请求
                    response = session.get(endpoint, timeout=30)
                    if response.status_code == 200:
                        success, message = self.check_checkin_response(response.text)
                        if success:
                            return True, message
                    
                    # POST请求
                    response = session.post(endpoint, data={'checkin': '1'}, timeout=30)
                    if response.status_code == 200:
                        success, message = self.check_checkin_response(response.text)
                        if success:
                            return True, message
                            
                except Exception as e:
                    self.logger.debug(f"账户 [{account_name}] API 端点 {endpoint} 失败: {str(e)}")
                    continue
            
            return False, "所有签到方法都失败"
            
        except Exception as e:
            return False, f"签到错误: {str(e)}"
    
    def analyze_and_checkin(self, session, html_content, page_url, account_name):
        """分析页面内容并执行签到"""
        # 检查是否已经签到
        if self.already_checked_in(html_content):
            return True, "今日已签到"
        
        # 检查是否需要签到
        if not self.is_checkin_page(html_content):
            return False, "不是签到页面"
        
        # 尝试POST签到
        try:
            checkin_data = {'checkin': '1', 'action': 'checkin', 'daily': '1'}
            
            # 提取CSRF token
            csrf_token = self.extract_csrf_token(html_content)
            if csrf_token:
                checkin_data['_token'] = csrf_token
                checkin_data['csrf_token'] = csrf_token
            
            response = session.post(page_url, data=checkin_data, timeout=30)
            
            if response.status_code == 200:
                return self.check_checkin_response(response.text)
                
        except Exception as e:
            self.logger.debug(f"[{account_name}] POST 签到失败: {str(e)}")
        
        return False, "执行签到失败"
    
    def already_checked_in(self, html_content):
        """检查是否已经签到"""
        content_lower = html_content.lower()
        indicators = [
            'already checked in', '今日已签到', 'checked in today',
            'attendance recorded', '已完成签到', 'completed today'
        ]
        return any(indicator in content_lower for indicator in indicators)
    
    def is_checkin_page(self, html_content):
        """判断是否是签到页面"""
        content_lower = html_content.lower()
        indicators = ['check-in', 'checkin', '签到', 'attendance', 'daily']
        return any(indicator in content_lower for indicator in indicators)
    
    def extract_csrf_token(self, html_content):
        """提取CSRF token"""
        import re
        patterns = [
            r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def check_checkin_response(self, html_content):
        """检查签到响应"""
        content_lower = html_content.lower()
        
        success_indicators = [
            'check-in successful', 'checkin successful', '签到成功',
            'attendance recorded', 'earned reward', '获得奖励',
            'success', '成功', 'completed'
        ]
        
        if any(indicator in content_lower for indicator in success_indicators):
            # 提取奖励信息
            import re
            reward_patterns = [
                r'获得奖励[^\d]*(\d+\.?\d*)\s*元',
                r'earned.*?(\d+\.?\d*)\s*(credits?|points?)',
                r'(\d+\.?\d*)\s*(credits?|points?|元)'
            ]
            
            for pattern in reward_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    reward = match.group(1)
                    return True, f"签到成功! 获得 {reward} 元"
            
            return True, "签到成功!"
        
        return False, "签到响应失败"
    
    def perform_token_checkin(self, account_data, account_name):
        """使用token执行签到"""
        if 'token_data' not in account_data:
            return False, "在配置文件中没有找到 token data 数据"
        
        try:
            session = self.create_session(account_data['token_data'])
            
            # 测试认证
            auth_result = self.test_authentication(session, account_name)
            if not auth_result[0]:
                return False, f"身份认证失败: {auth_result[1]}"
            
            # 执行签到
            return self.perform_checkin(session, account_name)
            
        except Exception as e:
            return False, f"Token 效验错误: {str(e)}"
    
    def run_all_accounts(self):
        """为所有账号执行token签到"""
        self.logger.info("=" * 60)
        self.logger.info("🔑 启动 LeafLow 自动签到")
        self.logger.info("=" * 60)
        success_count = 0
        total_count = 0
        results = []
        
        for account_index, account in enumerate(self.config['accounts']):
            if not account.get('enabled', True):
                self.logger.info(f"⏭️ 正在跳过已禁用的帐户：帐户 {account_index+1}")
                continue
                
            total_count += 1
            # 优先使用配置中的 'name' 字段，如果不存在则使用默认的 "账号N"
            account_name = account.get('name', f"账号{account_index + 1}") 
            self.logger.info(f"\n📋 正在处理 {account_name}...")
            
            success, message = self.perform_token_checkin(account, account_name)
            results.append({
                'account': account_name,
                'success': success,
                'message': message,
            })
            
            if success:
                self.logger.info(f"✅ 账户 [{account_name}] {message}")
                success_count += 1
            else:
                self.logger.error(f"❌ 账户 [{account_name}] {message}")
            
            # 账号间延迟
            if account_index < len(self.config['accounts']) - 1:
                delay = self.config['settings'].get('retry_delay', 5)
                self.logger.info(f"⏱️ 等待 {delay} 秒后开始签到下一个账号...")
                time.sleep(delay)
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info(f"🏁 签到已完成: {success_count}/{total_count} 成功")
        self.logger.info("=" * 60)
        
        return success_count, total_count, results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='LeafLow 自动签到脚本')
    parser.add_argument('--config', default='config.accounts.json', help='Configuration file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--notify', action='store_true', help='Enable notification push')
    parser.add_argument('--no-notify', action='store_true', help='Disable notification push')
    
    args = parser.parse_args()
    
    try:
        checkin = LeafLowTokenCheckin(args.config)
        
        if args.debug:
            import logging
            logging.getLogger().setLevel(logging.DEBUG)
            checkin.logger.info("🐛 启用调试模式")
        
        # 执行签到
        success_count, total_count, results = checkin.run_all_accounts()
        
        # 通知逻辑
        if args.notify or (not args.no_notify):
            try:
                from notify import send
                import os
                import json
                
                # 如果存在通知配置则加载
                notify_config = {}
                if os.path.exists('config.notify.json'):
                    with open('config.notify.json', 'r', encoding='utf-8') as f:
                        notify_config = json.load(f)
                
                # 构建通知内容
                title = "LeafLow 自动签到结果通知"
                content_lines = [f"🏁 签到已完成: {success_count}/{total_count} 成功\n"]
                
                for result in results:
                    status = "✅" if result['success'] else "❌"
                    content_lines.append(f"{status} {result['account']}: {result['message']}")
                
                content = "\n".join(content_lines)
                send(title, content, **notify_config)
                checkin.logger.info("📱 发送通知")
                
            except ImportError:
                checkin.logger.warning("⚠️ 未找到通知模块，跳过通知")
            except Exception as e:
                checkin.logger.error(f"❌ 发送通知失败: {str(e)}")
        
    except KeyboardInterrupt:
        print("\n\n⏸️ 用户中断程序")
    except Exception as e:
        print(f"\n\n💥 程序异常: {str(e)}")

if __name__ == "__main__":
    main()

