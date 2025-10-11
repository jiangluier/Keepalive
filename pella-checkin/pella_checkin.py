#!/usr/bin/env python3
"""
Pella 多账号自动续期脚本
支持冒号分隔多账号和单账号配置
"""

import os
import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PellaAutoRenew:
    # 配置class类常量
    LOGIN_URL = "https://www.pella.app/login"
    # 登录后会跳转到类似 https://www.pella.app/server/SERVER_ID 的页面
    RENEW_WAIT_TIME = 10  # 点击续期链接后在新页面等待的秒数
    WAIT_TIME_AFTER_LOGIN = 20  # 登录后等待的秒数
    RETRY_WAIT_TIME_PAGE_LOAD = 15 # 页面加载每次重试等待时间
    RETRY_COUNT_PAGE_LOAD = 3 # 页面加载重试次数

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.telegram_bot_token = os.getenv('TG_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TG_CHAT_ID', '')
        self.initial_expiry_days = -1
        self.server_url = None
        
        if not self.email or not self.password:
            raise ValueError("邮箱和密码不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动选项"""
        chrome_options = Options()
        
        # GitHub Actions环境配置
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
        
        # 通用配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def wait_for_element_clickable(self, by, value, timeout=10):
        """等待元素可点击"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def wait_for_element_present(self, by, value, timeout=10):
        """等待元素出现"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def extract_expiry_days(self, page_source):
        """从页面源码中提取过期天数"""
        # 正则表达式匹配 Your server expires in X.
        match = re.search(r"Your server expires in (\d+D)", page_source)
        if match:
            days_str = match.group(1).replace('D', '')
            return int(days_str)
        return -1 # 未找到或格式不匹配

    def login(self):
        """执行登录流程"""
        logger.info(f"🔑 开始登录流程")
        
        self.driver.get(self.LOGIN_URL)
        time.sleep(3)
        
        # 1. 输入邮箱
        try:
            logger.info("🔍 查找邮箱输入框...")
            # Pella 邮箱输入框 selector: input[name='identifier'] 或 input[type='text'][placeholder*='email']
            email_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[name='identifier']", 10)
            email_input.clear()
            email_input.send_keys(self.email)
            logger.info("✅ 邮箱输入完成")
            time.sleep(1)
        except Exception as e:
            raise Exception(f"❌ 输入邮箱时出错: {e}")
        
        # 2. 输入密码
        try:
            logger.info("🔍 查找密码输入框...")
            # Pella 密码输入框 selector: input[name='password'] 或 input[type='password'][placeholder*='password']
            password_input = self.wait_for_element_clickable(By.CSS_SELECTOR, "input[name='password']", 10)
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("✅ 密码输入完成")
            time.sleep(1)
        except TimeoutException:
            raise Exception("❌ 找不到密码输入框")
        
        # 3. 点击 Continue 按钮
        try:
            logger.info("🔍 查找 Continue 登录按钮...")
            # Pella 登录按钮 selector: button:has(span:contains('Continue')) 或 .cl-formButtonPrimary
            # 尝试使用 XPATH
            login_btn = self.wait_for_element_clickable(By.XPATH, "//button[contains(., 'Continue')]", 10)
            
            # 使用 JavaScript 点击，避免被 Captcha 覆盖导致点击无效
            self.driver.execute_script("arguments[0].click();", login_btn)
            logger.info("✅ 已点击 Continue 登录按钮")
            
        except Exception as e:
            raise Exception(f"❌ 点击 Continue 按钮失败: {e}")
        
        # 4. 等待登录完成并获取服务器页面 URL
        try:
            WebDriverWait(self.driver, self.WAIT_TIME_AFTER_LOGIN).until(
                lambda driver: "/server/" in driver.current_url
            )
            
            current_url = self.driver.current_url
            if "/server/" in current_url:
                self.server_url = current_url
                logger.info(f"✅ 登录成功，当前服务器URL: {self.server_url}")
                return True
            else:
                raise Exception("⚠️ 登录后未跳转到服务器页面")
                
        except TimeoutException:
            # 检查是否有错误消息，Pella 可能会在页面上显示错误
            try:
                error_msg = self.driver.find_element(By.CSS_SELECTOR, ".cl-auth-form-error-message, .cl-alert-danger")
                if error_msg.is_displayed():
                    raise Exception(f"❌ 登录失败: {error_msg.text}")
            except:
                pass
            raise Exception("⚠️ 登录超时，无法确认登录状态")

    def renew_server(self):
        """执行续期流程"""
        logger.info(f"👉 跳转到服务器页面: {self.server_url}")
        self.driver.get(self.server_url)
        time.sleep(5) # 基础等待

        # 1. 提取初始过期时间
        page_source = self.driver.page_source
        self.initial_expiry_days = self.extract_expiry_days(page_source)
        logger.info(f"ℹ️ 初始服务器过期时间: {self.initial_expiry_days} 天")

        if self.initial_expiry_days == -1:
             raise Exception("❌ 无法提取初始过期时间，可能页面加载失败或元素变化")

        # 2. 查找并点击所有续期按钮
        try:
            # 查找所有带有 href 且文本为 "Claim" 的 a 标签
            # 或者更精确地，查找 class 包含 rounded-md 的 a 标签，并排除 class 包含 pointer-events-none 的
            renew_link_selectors = "a.rounded-md:not(.pointer-events-none)"
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, renew_link_selectors))
            )
            
            renew_buttons = self.driver.find_elements(By.CSS_SELECTOR, renew_link_selectors)
            
            if not renew_buttons:
                # 再次尝试更通用的链接，查找 href 包含 /renew/ 的链接
                renew_buttons = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/renew/']")
                # 筛选掉已经 Claimed 的（即 class 中有 opacity-50 或 pointer-events-none 的）
                renew_buttons = [btn for btn in renew_buttons if 'opacity-50' not in btn.get_attribute('class') and 'pointer-events-none' not in btn.get_attribute('class')]

            if not renew_buttons:
                 return "⏳ 未找到可点击的续期按钮，可能今日已续期。"

            logger.info(f"👉 找到 {len(renew_buttons)} 个可点击的续期链接")
            
            renewed_count = 0
            original_window = self.driver.current_window_handle
            
            for i, button in enumerate(renew_buttons, 1):
                renew_url = button.get_attribute('href')
                logger.info(f"🚀 开始处理第 {i} 个续期链接: {renew_url}")
                
                # 在新标签页中打开链接
                self.driver.execute_script("window.open(arguments[0]);", renew_url)
                time.sleep(1)
                
                # 切换到新的标签页
                self.driver.switch_to.window(self.driver.window_handles[-1])
                logger.info(f"⏳ 在续期页面等待 {self.RENEW_WAIT_TIME} 秒...")
                time.sleep(self.RENEW_WAIT_TIME)
                
                # 关闭新标签页并切回主页面
                self.driver.close()
                self.driver.switch_to.window(original_window)
                logger.info(f"✅ 第 {i} 个续期链接处理完成")
                renewed_count += 1
                time.sleep(2) # 间隔一下

            # 3. 重新加载服务器页面并获取新的过期时间
            if renewed_count > 0:
                logger.info("🔄 重新加载服务器页面以检查续期结果...")
                self.driver.get(self.server_url)
                time.sleep(5)
                
                final_expiry_days = self.extract_expiry_days(self.driver.page_source)
                logger.info(f"ℹ️ 最终服务器过期时间: {final_expiry_days} 天")
                
                if final_expiry_days > self.initial_expiry_days:
                    return f"✅ 续期成功! 初始 {self.initial_expiry_days} 天 -> 最终 {final_expiry_days} 天 (共续期 {final_expiry_days - self.initial_expiry_days} 天)"
                elif final_expiry_days == self.initial_expiry_days:
                    return f"⚠️ 续期操作完成，但天数未增加 ({final_expiry_days} 天)。可能续期未生效或当天无额外时间。"
                else:
                    return f"❌ 续期操作完成，但天数不升反降! 初始 {self.initial_expiry_days} 天 -> 最终 {final_expiry_days} 天"
            else:
                 return "⏳ 未执行续期操作，因为没有找到可点击的续期链接。"

        except TimeoutException:
            raise Exception("❌ 页面元素加载超时")
        except NoSuchElementException as e:
             raise Exception(f"❌ 续期元素查找失败: {e}")
        except Exception as e:
            raise Exception(f"❌ 续期流程中出现意外错误: {e}")
            
    def run(self):
        """单个账号执行流程"""
        try:
            logger.info(f"⏳ 开始处理账号")
            
            # 登录
            if self.login():
                # 续期
                result = self.renew_server()
                logger.info(f"📋 续期结果: {result}")
                return True, result
            else:
                raise Exception("❌ 登录失败")
                
        except Exception as e:
            error_msg = f"❌ 自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        
        finally:
            if self.driver:
                self.driver.quit()

class MultiAccountManager:
    """多账号管理器 - 简化配置版本"""
    
    def __init__(self):
        self.telegram_bot_token = os.getenv('TG_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TG_CHAT_ID', '')
        self.accounts = self.load_accounts()
    
    def load_accounts(self):
        # 保持与 Leaflow 脚本兼容的加载逻辑，但使用 Pella 的环境变量名
        accounts = []
        logger.info("⏳ 开始加载账号配置...")
        
        # 方法1: 冒号分隔多账号格式 (使用 PELLA_ACCOUNTS 变量)
        accounts_str = os.getenv('PELLA_ACCOUNTS', os.getenv('LEAFLOW_ACCOUNTS', '')).strip()
        if accounts_str:
            try:
                logger.info("⏳ 尝试解析冒号分隔多账号配置")
                # 兼容逗号、分号分隔
                account_pairs = [pair.strip() for pair in re.split(r'[;,]', accounts_str)] 
                
                logger.info(f"👉 找到 {len(account_pairs)} 个账号对")
                
                for i, pair in enumerate(account_pairs):
                    if ':' in pair:
                        email, password = pair.split(':', 1)
                        email = email.strip()
                        password = password.strip()
                        
                        if email and password:
                            accounts.append({
                                'email': email,
                                'password': password
                            })
                            logger.info(f"✅ 成功添加第 {i+1} 个账号")
                        else:
                            logger.warning(f"❌ 账号对格式错误或内容为空")
                    else:
                        logger.warning(f"❌ 账号对缺少分隔符: {pair}")
                
                if accounts:
                    logger.info(f"👉 从多账号格式成功加载了 {len(accounts)} 个账号")
                    return accounts
                else:
                    logger.warning("⚠️ 多账号配置中没有找到有效的账号信息")
            except Exception as e:
                logger.error(f"❌ 解析多账号配置失败: {e}")
        
        # 方法2: 单账号格式 (使用 PELLA_EMAIL 和 PELLA_PASSWORD 变量)
        single_email = os.getenv('PELLA_EMAIL', os.getenv('LEAFLOW_EMAIL', '')).strip()
        single_password = os.getenv('PELLA_PASSWORD', os.getenv('LEAFLOW_PASSWORD', '')).strip()
        
        if single_email and single_password:
            accounts.append({
                'email': single_email,
                'password': single_password
            })
            logger.info("👉 加载了单个账号配置")
            return accounts
        
        # 如果所有方法都失败
        logger.error("⚠️ 未找到有效的账号配置")
        logger.error("⚠️ 请检查以下环境变量设置:")
        logger.error("⚠️ 1. PELLA_ACCOUNTS: 冒号分隔多账号 (email1:pass1,email2:pass2) 或使用 LEAFLOW_ACCOUNTS")
        logger.error("⚠️ 2. PELLA_EMAIL 和 PELLA_PASSWORD: 单账号 或使用 LEAFLOW_EMAIL/LEAFLOW_PASSWORD")
        
        raise ValueError("⚠️ 未找到有效的账号配置")
    
    def send_notification(self, results):
        """发送汇总通知到Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("⚠️ Telegram配置未设置，跳过通知")
            return
        
        try:
            # 统计结果
            success_count = sum(1 for _, success, result in results if success and "续期成功" in result)
            already_done_count = sum(1 for _, success, result in results if success and "未找到可点击" in result)
            failure_count = sum(1 for _, success, _ in results if not success)
            total_count = len(results)

            message = f"🎁 Pella自动续期通知\n\n"
            message += f"📋 共处理账号: {total_count} 个，其中：\n"
            message += f"📊 续期成功: {success_count} 个\n"
            message += f"📊 今日已续期: {already_done_count} 个\n"
            message += f"❌ 续期失败: {failure_count} 个\n\n"
            
            for email, success, result in results:
                if success and "续期成功" in result:
                    status = "✅" # 续期成功
                elif "未找到可点击" in result:
                    status = "⏳" # 已续期
                else:
                    status = "❌" # 失败
                
                # 隐藏邮箱部分字符以保护隐私
                masked_email = email[:3] + "***" + email[email.find("@"):]
                # 限制结果长度
                short_result = result.split('\n')[0][:100] + ('...' if len(result.split('\n')[0]) > 100 else '')
                message += f"{status} {masked_email}: {short_result}\n"
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Telegram 通知发送成功")
            else:
                logger.error(f"❌ Telegram 通知发送失败: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Telegram 通知发送出错: {e}")
    
    def run_all(self):
        """运行所有账号的续期流程"""
        logger.info(f"👉 开始执行 {len(self.accounts)} 个账号的续期任务")
        
        results = []
        
        for i, account in enumerate(self.accounts, 1):
            logger.info(f"👉 处理第 {i}/{len(self.accounts)} 个账号: {account['email']}")
            
            try:
                # 使用新的 PellaAutoRenew 类
                auto_renew = PellaAutoRenew(account['email'], account['password'])
                success, result = auto_renew.run()
                results.append((account['email'], success, result))
                
                # 在账号之间添加间隔，避免请求过于频繁
                if i < len(self.accounts):
                    wait_time = 5
                    logger.info(f"⏳ 等待{wait_time}秒后处理下一个账号...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                error_msg = f"❌ 处理账号时发生异常: {str(e)}"
                logger.error(error_msg)
                results.append((account['email'], False, error_msg))
        
        # 发送汇总通知
        self.send_notification(results)
        
        # 返回总体结果
        success_count = sum(1 for _, success, _ in results if success)
        return success_count == len(self.accounts), results

def main():
    """主函数"""
    try:
        manager = MultiAccountManager()
        overall_success, detailed_results = manager.run_all()
        
        if overall_success:
            logger.info("✅ 所有账号续期任务完成")
            exit(0)
        else:
            success_count = sum(1 for _, success, _ in detailed_results if success)
            logger.warning(f"⚠️ 部分账号续期失败: {success_count}/{len(detailed_results)} 成功")
            exit(0)
            
    except Exception as e:
        logger.error(f"❌ 脚本执行出错: {e}")
        exit(1)

if __name__ == "__main__":
    main()
