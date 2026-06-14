import lark_oapi as lark
# 关键：显式导入 ws 模块
import lark_oapi.ws as ws
from lark_oapi.api.im.v1 import *

# 1. 填入你的凭证
APP_ID = "cli_a9f2cbac9c791cb1"
APP_SECRET = "bBzwQ5eqYW4I0CxgpCiEwfXBxn37nTcu"

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