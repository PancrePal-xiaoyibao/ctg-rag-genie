# 如何配置feishu bot并接入clawdbot？

### 一句话

- 使用官方skills发布的应用，结合飞书自定义应用，进行长链接打通。偶尔会有延迟和不回答的问题，正常。期待后续完善。
- 期待微信/企业微信/钉钉的接入。

### brief info

Feishu Bridge
Connect a Feishu (Lark) bot to Clawdbot via WebSocket long-connection. No public server, domain, or ngrok required. Use when setting up Feishu/Lark as a messaging channel, troubleshooting the Feishu bridge, or managing the bridge service (start/stop/logs). Covers bot creation on Feishu Open Platform, credential setup, bridge startup, macOS launchd auto-restart, and group chat behavior tuning.

### 默认安装目录：

/Users/[root_user]/.nvm/versions/node/v22.19.0/lib/node_modules/clawdbot/skills/feishu-bridge-1.0.0

npx指令文档有，也可以下载后解压缩后复制过去。

### 记得！

npm install/node-set/node mjs 这些文档中指令，最好进入指定路径后操作，否则报错

## 配置文档

https://clawdhub.com/AlexAnys/feishu-bridge 按照这个skill的说明配置

---

### 比较特别的是，需要一个脚本，激活长链接，才能完成文档指引中添加event的动作，代码如下：

### feishu_bot.py

```
import lark_oapi as lark
# 关键：显式导入 ws 模块
import lark_oapi.ws as ws
from lark_oapi.api.im.v1 import *

# 1. 填入你的凭证
APP_ID = "飞书配置应用中获得"
APP_SECRET = "飞书配置应用中获得"

# 2. 定义处理逻辑
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    print(f"收到消息: {data.event.message.content}")

# 3. 构造事件处理器
handler = lark.EventDispatcherHandler.builder("", "") \
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
    .build()

# 4. 使用 ws.Client 启动长连接 (针对较新版 SDK)
client = ws.Client(APP_ID, APP_SECRET, event_handler=handler, log_level=lark.LogLevel.DEBUG)

if __name__ == "__main__":
    print("--- 正在启动长连接服务... ---")
    client.start()
```

### 日志参考：

```
--- 正在启动长连接服务... ---
[Lark] [2026-01-27 16:48:55,897] [ERROR] connect failed, err: 
[Lark] [2026-01-27 16:49:04,500] [INFO] trying to reconnect for the 1st time
[Lark] [2026-01-27 16:49:06,173] [INFO] connected to wss://msg-frontier.feishu.cn/ws/v2?fpid=493&aid=552564&device_id=7599960696613375161&access_key=cec98b948a7bd8735d322cd9a5dc52e1&service_id=33554678&ticket=39c7ddec-a7ad-48e7-951c-70d8acfdd9ae [conn_id=7599960696613375161]
[Lark] [2026-01-27 16:49:06,186] [DEBUG] ping success [conn_id=7599960696613375161]
[Lark] [2026-01-27 16:49:06,535] [DEBUG] receive pong [conn_id=7599960696613375161]
[Lark] [2026-01-27 16:50:36,199] [DEBUG] ping success [conn_id=7599960696613375161]
[Lark] [2026-01-27 16:50:36,549] [DEBUG] receive pong [conn_id=7599960696613375161]
```

调试通过，日志会有提示:

`FEISHU_APP_ID=cli_飞书获取的id node bridge.mjs`

```
[info]: [ 'client ready' ]
[info]: [ 'event-dispatch is ready' ]
[info]: [
  '[ws]',
  'receive events or callbacks through persistent connection only available in self-build & Feishu app, Configured in:\n' +
    '        Developer Console(开发者后台) \n' +
    '          ->\n' +
    '        Events and Callbacks(事件与回调)\n' +
    '          -> \n' +
    '        Mode of event/callback subscription(订阅方式)\n' +
    '          -> \n' +
    '        Receive events/callbacks through persistent connection(使用 长连接 接收事件/回调)'
]
[OK] Feishu bridge started (appId=cli_a9f2cbac9c791cb1)
[info]: [ '[ws]', 'ws client ready' ]
[info]: [ '[ws]', 'reconnect' ]
[info]: [ '[ws]', 'reconnect' ]
[info]: [ '[ws]', 'reconnect' ]
[info]: [ '[ws]', 'reconnect' ]
```


### 日志也可以看到

`tail -f ~/.clawdbot/logs/feishu-bridge.out.log  `

```




    '        Developer Console(开发者后台) \n' +
    '          ->\n' +
    '        Events and Callbacks(事件与回调)\n' +
    '          -> \n' +
    '        Mode of event/callback subscription(订阅方式)\n' +
    '          -> \n' +
    '        Receive events/callbacks through persistent connection(使用 长连接 接收事件/回调)'
]
[OK] Feishu bridge started (appId=cli_a9f2cbac9c791cb1)
[info]: [ '[ws]', 'ws client ready' ]
[error]: [
  AxiosError: Client network socket disconnected before secure TLS connection was established
      at TLSSocket.onConnectEnd (node:_tls_wrap:1732:19)
      at TLSSocket.emit (node:events:531:35)
      at endReadableNT (node:internal/streams/readable:1698:12)
      at process.processTicksAndRejections (node:internal/process/task_queues:90:21) {
    localAddress: undefined,
    port: 443,
    host: 'open.feishu.cn',
    path: null,
    code: 'ECONNRESET',
    config: {
      transitional: [Object],
      adapter: [Function: httpAdapter],
      transformRequest: [Array],
      transformResponse: [Array],
      timeout: 0,
      xsrfCookieName: 'XSRF-TOKEN',
      xsrfHeaderName: 'X-XSRF-TOKEN',
      maxContentLength: -1,
      maxBodyLength: -1,
      env: [Object],
      validateStatus: [Function: validateStatus],
      headers: [Object],
      method: 'post',
      url: 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
      data: '{"app_id":"cli_a9f2cbac9c791cb1","app_secret":"bBzwQ5eqYW4I0CxgpCiEwfXBxn37nTcu"}'
    },
    request: Writable {
      _events: [Object],
      _writableState: [WritableState],
      _maxListeners: undefined,
      _options: [Object],
      _ended: false,
      _ending: true,
      _redirectCount: 0,
      _redirects: [],
      _requestBodyLength: 81,
      _requestBodyBuffers: [Array],
      _eventsCount: 3,
      _onNativeResponse: [Function (anonymous)],
      _currentRequest: [ClientRequest],
      _currentUrl: 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
      [Symbol(shapeMode)]: true,
      [Symbol(kCapture)]: false
    }
  }
]

```

就基本成功了。

### 命令汇总

参考文档，记得进入skills目录操作。
