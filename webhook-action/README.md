这是一个 Cloudflare Worker 脚本，用于接收来自 Uptime Kuma 的 Webhook 请求，并将其转发到 GitHub Actions 进行处理。

请确保在 Cloudflare Worker 的环境变量(Secrets)中设置以下变量：

- `GITHUB_TOKEN` = <您的GitHub Personal Access Token>，该令牌需要有触发 GitHub Actions 的权限
- `SECRET_TOKEN` = <设置的密码>，用于验证请求来源，以保护API端点的安全

部署此脚本后，将 Uptime Kuma 的 Webhook URL 设置为：

```
https://<Worker地址>?token=<设置的密码>&user=<GitHub用户名>&repo=<GitHub仓库名>
```
