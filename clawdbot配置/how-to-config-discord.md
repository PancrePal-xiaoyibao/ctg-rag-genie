下面给你一份中文的、可操作的配置指南，教你如何把 Clawdbot 加到 Discord 并使用其能力（最小可用配置、权限/意图、允许列表与路由、启动与验证、常见故障排查）。步骤按先后顺序，包含可直接复制的配置示例。

1) 在 Discord Developer Portal 创建 Bot
- 访问 Discord Developer Portal → Applications → New Application。
- 在应用中点 Bot → Add Bot，然后复制 Bot Token（这是后续要配置在 Clawdbot 的密钥）。

2) 在 Developer Portal 启用必要的 Privileged Gateway Intents
- 在应用的 Bot 页面，开启：
  - Message Content Intent（必需，否则在大多数公会频道无法读取消息文本）
  - Server Members Intent（推荐，用于用户查找和 allowlist）
- 如果不开这些，Clawdbot 会报“Used disallowed intents”或连不上消息内容。

3) 生成邀请链接并邀请 Bot 到你的服务器
- 在 OAuth2 → URL Generator：
  - 选择 scope: bot（可选 applications.commands，如果你需要 slash 命令）。
  - 在 Bot Permissions 选择读取/发送消息需要的权限，最常用：View Channels (Read Messages/View Channels)、Send Messages、Read Message History。根据需要再勾选 Attach Files / Embed Links / Manage Messages 等。
- 用生成的 URL 把 Bot 邀请到目标 Guild/频道。

4) 获取 Guild / Channel / User ID（用于配置）
- 在 Discord 设置中启用 Developer Mode（用户设置 → 高级 → 开发者模式）。
- 右键公会、频道或用户 → Copy ID，得到数字 ID 字符串（用于 config 中的键或 allowlists）。

5) 在 Clawdbot 中配置 Bot Token（两种方式）
- 推荐：把 token 设置为环境变量（适合服务器/daemon）：
  - export DISCORD_BOT_TOKEN="你的_bot_token"
- 或者在 Clawdbot 配置文件里设置（优先级：config > env）：
```json5
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN"
    }
  }
}
```

6) 最小可用示例（只在一个服务器的 #help 频道允许）
```json5
{
  "channels": {
    "discord": {
      "enabled": true,
      "dm": { "enabled": false },
      "guilds": {
        "YOUR_GUILD_ID": {
          "users": ["YOUR_USER_ID"],         // 只允许某些用户（可选）
          "requireMention": true,           // 需要提及 bot 才会回复（推荐共享频道开启）
          "channels": {
            "help": { "allow": true, "requireMention": true } // 使用 channel slug（lowercase, 空格->-）
          }
        }
      },
      "retry": {
        "attempts": 3,
        "minDelayMs": 500,
        "maxDelayMs": 30000,
        "jitter": 0.1
      }
    }
  }
}
```
说明：
- 当你在 config 中使用 guild 字段时，未列出的频道默认被拒绝（更安全）。
- 可以用 channel slug（频道名去小写、空格换成 -）或直接用频道 ID（更稳妥，避免改名问题）。
- requireMention: true 意味着 bot 只会在被 @ 提及时回复（避免在公共频道刷屏）。

7) DM（私聊）行为与配对
- 默认 DM 使用 pairing 模式：首次用户向 bot 发送 DM 时会发配对码，需要在 Clawdbot 的管理端/日志中批准（防止未授权访问）。
- 若你想允许所有人直接 DM（不建议公共服务），配置 channels.discord.dm.allowFrom 或把 dm.enabled 设为 true 并调整 allowFrom。

8) 多账号 / 多 token 支持
- 如果要运行多个 Discord 账户/机器人，可使用 channels.discord.accounts 列表，为每个账号提供 token 和 name（见 docs/gateway/configuration）。

9) 安装与启动 Clawdbot（快速）
- 在服务器上（示例来源仓库文档），可以先安装 Node.js 22，然后：
  - curl -fsSL https://clawd.bot/install.sh | bash
  - 验证： clawdbot --version
- 使用 onboarding 向导（会帮你配置模型 key、通道、daemon 等）：
  - clawdbot onboard --install-daemon
- 启动/检查 gateway 服务：
  - systemctl --user status clawdbot-gateway.service
  - journalctl --user -u clawdbot-gateway.service -f
  - 或使用 clawdbot 自带的命令查看状态（onboard 会提示下一步）。

10) 验证 Bot 是否工作
- 检查日志（journalctl、clawdbot 日志），确认 gateway 已连接且 Discord token 被识别。
- 在被允许的频道 mention bot 试发消息，看是否有回复。
- 在 DM 中第一次联系时，观察是否需要配对批准并按提示操作。

11) 常见问题和排查
- “Bot 连上了但不回复”：
  - 检查是否开启了 Message Content Intent（没有会无法读取消息正文）。
  - 检查 config 中 requireMention 是否为 true（需要 @）。
  - 确认 guild/channel/user 是否在 allowlist（如果设置了 channels 配置）。
- “Used disallowed intents” 或 权限错误：
  - 在 Developer Portal 确认启用了 Message Content 与 Server Members Intent。
  - 再重新重启 Clawdbot gateway。
- “无法获取正确 channel id/slug”：
  - 在 Discord 启用 Developer Mode 并 Copy ID，或者在 config 中用 slug（注意小写与空格转 -）。
- “Bot 看不到旧消息或文件”：
  - 确认 Bot 拥有 Read Message History，若需要文件传输确认 allowUploads 等设置（可参考 docs）。
- 防止 Bot 循环回复其它 bot：
  - 默认 bot 自己发的消息被忽略；如果你启用 channels.discord.allowBots=true，需要小心设置 requireMention/allowlists 防止回路。

12) 高级：按频道/线程继承、agents 覆盖
- 线程会继承父频道的配置，除非你在 config 指定线程 id。
- 可以为单个 agent 配置 groupChat.mentionPatterns 来覆盖 per-guild mention 行为（用于更复杂的路由）。

参考文档位置（项目仓库中已有详细说明）：
- docs/channels/discord.md — 包含快速开始、创建 bot、启用 intents、配置示例与故障排查片段。
- docs/gateway/configuration.md — 解释 channels.discord 配置项与交付目标语法（user:<id> / channel:<id>）。
- README.md 中也列出 Discord channel 的简要配置示例。
