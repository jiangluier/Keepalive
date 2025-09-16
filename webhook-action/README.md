## 部署 worker api

这是一个 Cloudflare Worker 脚本，用于接收来自 Uptime Kuma 的 Webhook 请求，并将其转发到 GitHub Actions 进行处理。

请确保在 Cloudflare Worker 的环境变量(Secrets)中设置以下变量：

- `GITHUB_TOKEN` = <您的GitHub Personal Access Token>，该令牌需要有触发 GitHub Actions 的权限
- `SECRET_TOKEN` = <设置的密码>，用于验证请求来源，以保护API端点的安全

部署此脚本后，将 Uptime Kuma 的 Webhook URL 设置为：

```
https://<Worker地址>?token=<设置的密码>&user=<GitHub用户名>&repo=<GitHub仓库名>
```

## 修改目标仓库 action 的触发方式

```yml
name: your action

on:
  workflow_dispatch:
  # schedule:
  #   - cron: '0 */2 * * *'

  # 当 Uptime Kuma API 发送 'service-down-alert' 事件时触发此工作流。
  repository_dispatch:
    types: [service-down-alert]

jobs:
  deploy-and-sync:
    runs-on: ubuntu-latest
    ..............

    steps:
      - name: Check Trigger Event
        run: |
          echo "Workflow triggered by: ${{ github.event_name }}"
          if [[ "${{ github.event_name }}" == "repository_dispatch" ]]; then
            echo "触发事件类型 (Event Type): ${{ github.event.action }}"
            echo "收到来自 Uptime Kuma 的下线通知，开始执行自动恢复部署流程..."
          elif [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo "工作流被手动触发，开始执行部署..."
          else
            echo "工作流由计划任务触发，开始执行部署..."
          fi
    ..............
```

## 手动测试

在终端中运行以下代码：

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{ "heartbeat": { "status": 0, "msg": "来自curl的手动测试", "time": "2025-09-16T00:00:00Z" }, "monitor": { "name": "手动验证监控" }, "msg": "这是一条手动验证通知。" }' \
  'https://<Worker地址>?token=<设置的密码>&user=<GitHub用户名>&repo=<GitHub仓库名>'
```

## 完整测试

- 登录 Uptime Kuma
- 创建一个临时的监控项：
  - 点击 `添加新的监控项`
  - 监控项类型选择 `HTTP(s) - 关键字`
  - URL: 填写一个肯定存在的网站，例如 `https://www.google.com`
  - 关键字: 填写一个绝对不会在该网站上出现的词，例如 `_这是一个用于测试的绝对不存在的关键字_`
  - 心跳间隔: 为了快速看到结果，可以临时设置为 20 秒。
- 关联通知渠道：确保已经配置好 Webhook URL：`https://<Worker地址>?token=<设置的密码>&user=<GitHub用户名>&repo=<GitHub仓库名>`
- 保存并观察
