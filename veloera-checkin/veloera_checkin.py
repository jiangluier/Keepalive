#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veloera 通用签到服务
====================
支持多平台、多用户、配置驱动的自动化签到系统
"""

import os
import json
import logging
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urljoin


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class CheckinStatus(Enum):
    """签到状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    ALREADY_CHECKED = "already_checked"
    UNAUTHORIZED = "unauthorized"
    NETWORK_ERROR = "network_error"


@dataclass
class CheckinResult:
    """签到结果数据类"""
    status: CheckinStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class VeloeraConfig:
    """Veloera 配置数据类"""
    base_url: str
    user_id: str
    access_token: str
    checkin_endpoint: str = "/api/user/check_in"
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    
    @property
    def checkin_url(self) -> str:
        """获取完整的签到URL"""
        return urljoin(self.base_url, self.checkin_endpoint)


class Logger:
    """企业级日志管理器"""
    
    def __init__(self, name: str = "VeloeraCheckin", level: LogLevel = LogLevel.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        
        if not self.logger.handlers:
            # 控制台处理器
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str) -> None:
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        self.logger.error(message)
    
    def critical(self, message: str) -> None:
        self.logger.critical(message)


class BaseCheckinService(ABC):
    """签到服务抽象基类"""
    
    def __init__(self, config: VeloeraConfig, logger: Logger):
        self.config = config
        self.logger = logger
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        session.headers.update(self._get_default_headers())
        return session
    
    @abstractmethod
    def _get_default_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        pass
    
    @abstractmethod
    def _parse_response(self, response: requests.Response) -> CheckinResult:
        """解析响应数据"""
        pass
    
    def checkin(self) -> CheckinResult:
        """执行签到操作"""
        self.logger.info("🚀 开始执行签到操作...")
        
        for attempt in range(1, self.config.retry_count + 1):
            try:
                self.logger.debug(f"第 {attempt} 次尝试签到")
                
                response = self.session.post(
                    self.config.checkin_url,
                    timeout=self.config.timeout
                )
                
                result = self._parse_response(response)
                
                if result.status == CheckinStatus.SUCCESS:
                    self.logger.info(f"✅ {result.message}")
                    return result
                elif result.status == CheckinStatus.ALREADY_CHECKED:
                    self.logger.info(f"ℹ️ {result.message}")
                    return result
                elif result.status == CheckinStatus.UNAUTHORIZED:
                    self.logger.error(f"🔒 认证失败: {result.message}")
                    return result  # 认证失败不需要重试
                else:
                    self.logger.warning(f"⚠️ 第 {attempt} 次尝试失败: {result.message}")

                    if attempt < self.config.retry_count:
                        import time
                        time.sleep(self.config.retry_delay)
                    
            except requests.exceptions.Timeout:
                self.logger.error(f"❌ 第 {attempt} 次尝试超时")
            except requests.exceptions.RequestException as e:
                self.logger.error(f"❌ 第 {attempt} 次尝试网络异常: {e}")
            except Exception as e:
                self.logger.error(f"❌ 第 {attempt} 次尝试未知错误: {e}")
        
        return CheckinResult(
            status=CheckinStatus.FAILED,
            message="所有重试尝试均失败",
            error_code="MAX_RETRY_EXCEEDED"
        )


class VeloeraCheckinService(BaseCheckinService):
    """Veloera 签到服务实现"""

    def _is_already_checked_message(self, message: str) -> bool:
        """检查消息是否表示已经签到过"""
        already_checked_keywords = [
            "已经签到",
            "已签到",
            "重复签到",
            "今天已经签到过了",
            "already checked",
            "already signed"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in already_checked_keywords)

    def _get_default_headers(self) -> Dict[str, str]:
        """获取 Veloera 平台默认请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:140.0) Gecko/20100101 Firefox/140.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Authorization': f'Bearer {self.config.access_token}',
            'Veloera-User': self.config.user_id,
            'Cache-Control': 'no-store',
            'Origin': self.config.base_url,
            'Connection': 'keep-alive',
            'Referer': f'{self.config.base_url}/personal',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Priority': 'u=0',
            'Pragma': 'no-cache',
            'Content-Length': '0',
            'TE': 'trailers'
        }
    
    def _parse_response(self, response: requests.Response) -> CheckinResult:
        """解析 Veloera 平台响应"""
        try:
            if response.status_code == 200:
                data = response.json()

                if data.get('success'):
                    quota = data.get('data', {}).get('quota', 0)
                    message = data.get('message', '签到成功')

                    # 格式化配额显示
                    quota_mb = quota / (1024 * 1024) if quota else 0
                    formatted_message = f"{message} - 当前配额: {quota_mb:.2f} MB"

                    return CheckinResult(
                        status=CheckinStatus.SUCCESS,
                        message=formatted_message,
                        data={'quota': quota, 'quota_mb': quota_mb}
                    )
                else:
                    error_msg = data.get('message', '签到失败')

                    # 检查是否为已签到的情况
                    if self._is_already_checked_message(error_msg):
                        return CheckinResult(
                            status=CheckinStatus.ALREADY_CHECKED,
                            message=error_msg,
                            error_code="ALREADY_CHECKED"
                        )

                    return CheckinResult(
                        status=CheckinStatus.FAILED,
                        message=error_msg,
                        error_code=data.get('code')
                    )
            
            elif response.status_code == 401:
                return CheckinResult(
                    status=CheckinStatus.UNAUTHORIZED,
                    message="认证失败，请检查访问令牌和用户ID",
                    error_code="UNAUTHORIZED"
                )
            
            else:
                return CheckinResult(
                    status=CheckinStatus.FAILED,
                    message=f"HTTP错误 {response.status_code}: {response.text}",
                    error_code=f"HTTP_{response.status_code}"
                )
                
        except json.JSONDecodeError as e:
            return CheckinResult(
                status=CheckinStatus.FAILED,
                message=f"响应JSON解析失败: {e}",
                error_code="JSON_DECODE_ERROR"
            )
        except Exception as e:
            return CheckinResult(
                status=CheckinStatus.FAILED,
                message=f"响应解析异常: {e}",
                error_code="PARSE_ERROR"
            )


class ConfigManager:
    """配置管理器"""

    @staticmethod
    def load_from_env(platform: str = "miaogeapi") -> VeloeraConfig:
        """从环境变量加载配置"""
        platform_upper = platform.upper()

        # 环境变量映射
        env_mapping = {
            'base_url': f'{platform_upper}_BASE_URL',
            'user_id': f'{platform_upper}_USER_ID',
            'access_token': f'{platform_upper}_TOKEN',
            'checkin_endpoint': f'{platform_upper}_CHECKIN_ENDPOINT',
            'timeout': f'{platform_upper}_TIMEOUT',
            'retry_count': f'{platform_upper}_RETRY_COUNT',
            'retry_delay': f'{platform_upper}_RETRY_DELAY'
        }

        # 默认配置
        defaults = {
            'miaogeapi': {
                # 'base_url': 'https://miaogeapi.deno.dev',
                'base_url': 'https://linjinpeng-new-api.hf.space',
                'user_id': '159',
                'checkin_endpoint': '/api/user/check_in',
                'timeout': 30,
                'retry_count': 3,
                'retry_delay': 1.0
            }
        }

        platform_defaults = defaults.get(platform, {})

        # 构建配置
        config_data = {}
        for key, env_key in env_mapping.items():
            value = os.getenv(env_key)
            if value is None:
                if key in platform_defaults:
                    value = platform_defaults[key]
                elif key == 'access_token':
                    raise ValueError(f"必需的环境变量 {env_key} 未设置")
                else:
                    continue

            # 类型转换
            if key in ['timeout', 'retry_count']:
                value = int(value)
            elif key == 'retry_delay':
                value = float(value)

            config_data[key] = value

        return VeloeraConfig(**config_data)

    @staticmethod
    def load_from_file(config_path: str) -> List[VeloeraConfig]:
        """从配置文件加载多个配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        configs = []
        for item in data.get('accounts', []):
            configs.append(VeloeraConfig(**item))

        return configs


class VeloeraCheckinManager:
    """Veloera 签到管理器"""

    def __init__(self, logger: Optional[Logger] = None):
        self.logger = logger or Logger()
        self.configs: List[VeloeraConfig] = []  # 存储配置以便后续使用

    def run_single_checkin(self, config: VeloeraConfig) -> CheckinResult:
        """执行单个账号签到"""
        service = VeloeraCheckinService(config, self.logger)
        return service.checkin()

    def run_batch_checkin(self, configs: List[VeloeraConfig]) -> List[CheckinResult]:
        """执行批量账号签到"""
        self.configs = configs  # 保存配置以便后续使用
        results = []

        self.logger.info(f"开始批量签到，共 {len(configs)} 个账号")

        for i, config in enumerate(configs, 1):
            self.logger.info(f"正在处理第 {i} 个账号 (用户ID: {config.user_id})")
            result = self.run_single_checkin(config)
            results.append(result)

            # 账号间延迟
            if i < len(configs):
                import time
                time.sleep(2)

        return results

    def print_summary(self, results: List[CheckinResult]) -> None:
        """打印签到结果摘要"""
        success_count = sum(1 for r in results if r.status == CheckinStatus.SUCCESS)
        already_checked_count = sum(1 for r in results if r.status == CheckinStatus.ALREADY_CHECKED)
        failed_count = len(results) - success_count - already_checked_count

        self.logger.info("=" * 60)
        self.logger.info("📊 签到结果摘要")
        self.logger.info("=" * 60)
        self.logger.info(f"✅ 新签到成功: {success_count} 个账号")
        self.logger.info(f"ℹ️ 今日已签到: {already_checked_count} 个账号")
        self.logger.info(f"❌ 签到失败: {failed_count} 个账号")

        # 显示详细信息
        if success_count > 0:
            self.logger.info("\n✅ 新签到成功详情:")
            for i, result in enumerate(results, 1):
                if result.status == CheckinStatus.SUCCESS:
                    user_id = self._get_user_id_from_index(i-1)
                    self.logger.info(f"  账号 {i} (用户ID: {user_id}): {result.message}")

        if already_checked_count > 0:
            self.logger.info("\nℹ️ 今日已签到详情:")
            for i, result in enumerate(results, 1):
                if result.status == CheckinStatus.ALREADY_CHECKED:
                    user_id = self._get_user_id_from_index(i-1)
                    self.logger.info(f"  账号 {i} (用户ID: {user_id}): {result.message}")

        if failed_count > 0:
            self.logger.info("\n❌ 签到失败详情:")
            for i, result in enumerate(results, 1):
                if result.status not in [CheckinStatus.SUCCESS, CheckinStatus.ALREADY_CHECKED]:
                    user_id = self._get_user_id_from_index(i-1)
                    self.logger.error(f"  账号 {i} (用户ID: {user_id}): {result.message}")

    def _get_user_id_from_index(self, index: int) -> str:
        """从结果索引获取用户ID（用于显示）"""
        if index < len(self.configs):
            return self.configs[index].user_id
        return f"用户{index + 1}"


def main():
    """主程序入口"""
    logger = Logger()
    manager = VeloeraCheckinManager(logger)

    logger.info("=" * 60)
    logger.info("🚀 Veloera 通用签到服务启动")
    logger.info("=" * 60)

    try:
        # 检查是否有配置文件
        config_file = os.getenv('VELOERA_CONFIG_FILE')

        if config_file and os.path.exists(config_file):
            # 从配置文件加载多账号
            logger.info(f"从配置文件加载: {config_file}")
            configs = ConfigManager.load_from_file(config_file)
            results = manager.run_batch_checkin(configs)
        else:
            # 从环境变量加载单账号
            logger.info("从环境变量加载配置")
            config = ConfigManager.load_from_env()
            result = manager.run_single_checkin(config)
            results = [result]

        # 打印摘要
        manager.print_summary(results)

        # 检查是否有真正失败的签到（排除已签到的情况）
        failed_count = sum(1 for r in results if r.status not in [CheckinStatus.SUCCESS, CheckinStatus.ALREADY_CHECKED])
        success_count = sum(1 for r in results if r.status == CheckinStatus.SUCCESS)
        already_checked_count = sum(1 for r in results if r.status == CheckinStatus.ALREADY_CHECKED)

        if failed_count > 0:
            logger.error(f"有 {failed_count} 个账号签到失败")
            exit(1)
        elif success_count > 0 and already_checked_count > 0:
            logger.info(f"🎉 签到任务完成！新签到 {success_count} 个账号，{already_checked_count} 个账号今日已签到")
        elif success_count > 0:
            logger.info(f"🎉 签到任务完成！成功签到 {success_count} 个账号")
        elif already_checked_count > 0:
            logger.info(f"ℹ️ 签到任务完成！所有 {already_checked_count} 个账号今日均已签到")
        else:
            logger.info("🎉 签到任务完成")

    except Exception as e:
        logger.critical(f"程序执行异常: {e}")
        exit(1)

    logger.info("=" * 60)

if __name__ == "__main__":
    main()
