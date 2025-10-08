# LeafLow 多账号自动签到脚本

## ✨ 特性

- 🔐 **Token-based 认证**：基于 Cookie/Token 认证，绕过复杂的登录流程
- 🖥️ **服务器友好**：无需浏览器环境，纯 HTTP 请求实现
- 👥 **多账号支持**：支持批量管理多个账号
- 📊 **详细日志**：完整的操作日志和调试信息
- 🔔 **通知推送**：支持 Telegram、企业微信等多种通知方式
- ⚡ **自动重试**：智能错误处理和重试机制
- 🎯 **积分统计**：自动提取和显示获得的积分
- 🛡️ **安全可靠**：支持 CSRF Token 自动处理

## action 仓库变量

### 必须变量：`LEAFLOW_COOKIES`

**格式为 `账号名|完整的cookie字符串`**，示例：

```
张三|cookie_string_for_zhangsan
李四|cookie_string_for_lisi
```

### 可选变量

- QYWX_KEY：用于企业微信通知
- TG_BOT_TOKEN：用于TG通知
- TG_CHAT_ID：用于TG通知

**执行 `LeafLow自动签到.yml` action，即可实现每日自动签到！**

---

## 基本逻辑

### 1. action 先执行 `get_tokens_hlep.py`

**生成 `config.accounts.json` 文件，储存账号信息**，格式如下：

`config.accounts.json` 格式

```json
{
  "settings": {
    "log_level": "INFO",
    "retry_delay": 5,
    "timeout": 30,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
  },
  "accounts": [
    {
      "name": "张三",
      "token_data": {
        "cookies": {
          "leaflow_session": "your_session_token",
          "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d": "your_remember_token",
          "XSRF-TOKEN": "your_csrf_token"
        }
      }
    },
    {
      "name": "李四",
      "token_data": {
        "cookies": {
          "leaflow_session": "your_session_token",
          "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d": "your_remember_token",
          "XSRF-TOKEN": "your_csrf_token"
        }
      }
    }
  ]
}
```

### 2. 再执行 `checkin_token.py`

- 解析 `config.accounts.json`
- 执行签到
- 发送通知

---

## 如何获取 cookie

1. 在浏览器中登录 [LeafLow](https://leaflow.net)
2. 按 `F12` 打开开发者工具，切换到 `Network`（网络）标签页
3. 刷新页面，在请求列表中找到主站的请求（例如 `leaflow.net`）
4. 在右侧的 `Headers` 标签页中，找到 `Request Headers` 下的 `cookie` 字段，并复制其完整内容。

**注意1：获取多账号cookie请使用浏览器无痕模式，不要登出现有的账号，一旦登出，cookie就失效了**
**注意2：新账号需要登录网页，在网页手动执行一次签到，再获取cookie，否则cookie无效**

---

## 🛠️ 工具说明

### checkin_token.py
主要的签到脚本，支持：
- Token-based 认证
- 多账号批量处理
- 自动签到检测
- 错误重试机制

### get_tokens_helper.py
Token 获取辅助工具：
- 解析 cURL 命令
- 提取 Cookies 和 Headers
- 生成配置条目

### notify.py
通知推送模块，支持：
- Telegram Bot 推送
- 企业微信机器人推送
- 控制台输出
- 一言随机句子

## 🔧 参数说明

### 命令行参数

```bash
python3 checkin_token.py [options]

Options:
  --config FILE    指定配置文件路径
  --debug          启用调试模式
  --notify         启用通知推送
  --no-notify      禁用通知推送
```

## 感谢

原仓库：https://github.com/keggin-CHN/leaflow-checkin  

原项目 action 方式不支持多账号，只有本地运行可以  
且本地运行需要先手动运行 `get_tokens_helper.py` 为每一个账号生成 `config.accounts.json` 
再将多账号的 `config.accounts.json` 拼接成一个，才可以实现批量签到  
也不支持账号信息的 `name` 字段，也就是说通知消息里，无法区分是哪个账号签到成功了

本项目将所有手动过程（除了获取登录cookie需要手动外）全部自动化了！

