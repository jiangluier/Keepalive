## 注意

https://miaogeapi.deno.dev 服务已停止，此签到脚本仅作为 VELOERA 项目的示例模版

## 多用户签到

- 变量名：VELOERA_CONFIG_JSON
- 格式示例

```json
{
  "accounts": [
    {
      "base_url": "https://miaogeapi.deno.dev",
      "user_id": "用户1的ID",
      "access_token": "用户1的访问令牌"
    },
    {
      "base_url": "https://miaogeapi.deno.dev",
      "user_id": "用户2的ID",
      "access_token": "用户2的访问令牌"
    },
    {
      "base_url": "https://some-other-veloera.com",
      "user_id": "用户3的ID",
      "access_token": "用户3的访问令牌"
    }
  ]
}
```

## 单用户签到变量
- MIAOGEAPI_USER_ID：账户 ID
- MIAOGEAPI_TOKEN：系统访问令牌，不是api令牌


