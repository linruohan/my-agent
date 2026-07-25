# Gateway 多通道

外部消息经 Gateway 进入 Agent，再把回复投递回原通道。

## 启用

`config/app.yaml`（或 `data/user_settings.yaml` 覆盖）：

```yaml
gateway:
  enabled: true
  http_enabled: true
  http_host: "127.0.0.1"
  http_port: 8765
  http_token: "change-me"
  http_webhook_url: ""   # 可选出站推送
  remote_hitl: ask       # auto_reject | approve_low | approve_medium | ask
```

## HTTP API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/message` | 入站：`{"text","source","chat_id"}` |
| GET | `/api/outbound` | 轮询出站消息（无 webhook 时使用） |

鉴权：`Authorization: Bearer <http_token>` 或 `?token=`。

### 出站 Webhook

配置 `http_webhook_url` 后，对 HTTP 等非 Telegram/Discord/Slack 通道的回复会优先：

```http
POST <http_webhook_url>
Content-Type: application/json
Authorization: Bearer <http_token>   # 若配置了 token

{"source":"http","chat_id":"...","text":"..."}
```

失败时回退到 `/api/outbound` 轮询队列。

## 安全建议

- **强制**：`enabled: true` 且 `http_enabled: true` 时必须设置非空 `http_token`，否则 HTTP 服务不会启动并记 error 日志
- 仅绑定 `127.0.0.1` 或置于反向代理之后，并由代理终止 TLS
- Discord/Slack 频道消息需 @mention 机器人才会入站

## 远程 HITL

| `remote_hitl` | 行为 |
|---------------|------|
| `auto_reject` | 敏感操作一律拒绝 |
| `approve_low` / `approve_medium` | 按风险自动批 |
| `ask` | 远程回复 `/approve` 或 `/reject` |

## 源码

```
src/gateway/
├── service.py      # 调度与投递
├── http_server.py  # HTTP API
├── telegram_bot.py # PollingGateway
├── discord_bot.py
├── slack_bot.py
└── inbox.py        # SQLite 收件箱（app.db）
```
