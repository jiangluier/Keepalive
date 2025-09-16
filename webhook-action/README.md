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

## uptime 设置

### 在uptime通知中设置webhook

- **显示名称**：填一个易于分辨的名称，如 `SAP离线`
- **通知类型**: `Webhook`
- **Post URL**: `https://<你的Worker地址>?token=<你的密码>&user=<你的用户名>&repo=<你的仓库名>` (请确保此URL完整且正确)
- **请求体**: 选择 `预设 - application/json` (然后不要在下方出现的任何文本框中填写内容)
- **额外 Header**: 保持 `禁用` 状态
- **保存**

### 修改监控项

- **监控项类型**：选择 `HTTP(s) - 关键字`
- **URL**: 填写监控的网站，如 `https://webapp.ap21.hana.ondemand.com`
- **关键字**: 填写一个在网站上必然出现的词，例如 `Hello`（注意大小写）
- **心跳间隔**: 建议 `3600` 秒，即1小时
- **通知**：关联刚刚设置的 `SAP离线` 通知
- **其他默认，点击保存**
