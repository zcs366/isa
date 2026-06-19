#!/usr/bin/env python3
"""
ISA v0.3.0 频道适配器

频道 = 通信管道。
ISA不依赖任何平台——频道是ISA与外部世界之间的桥梁。

内置频道：
  - cli: 标准输入输出（默认可用）
  - null: 空频道（静默）

开发者可在此文件添加新频道适配器。
只需继承ChannelAdapter，实现 send() 和 start()，
然后注册到 ISA 频道适配器列表中即可。

设计原则：
  - send(msg): 通过此频道发消息给用户/设备
  - start(on_message): 从此频道收消息，注入ISA总线
  - 每个频道运行在自己线程中
"""

# ChannelAdapter 和所有内置频道已在 isa.py 中定义
from isa import ChannelAdapter, CliChannel, NullChannel, CHANNEL_REGISTRY

# ============================================================
# 未来频道适配器模板（接口已留好）
# ============================================================

# class WechatChannel(ChannelAdapter):
#     """微信频道适配器"""
#     name = "wechat"
#
#     def send(self, msg):
#         # 通过微信公众号API发送
#         pass
#
#     def start(self, on_message):
#         # 启动微信消息接收（webhook或轮询）
#         pass


# class TelegramChannel(ChannelAdapter):
#     """Telegram频道适配器"""
#     name = "telegram"
#
#     def send(self, msg):
#         # 通过Telegram Bot API发送
#         pass
#
#     def start(self, on_message):
#         # 启动Telegram长轮询
#         pass


# class YuanbaoChannel(ChannelAdapter):
#     """元宝频道适配器"""
#     name = "yuanbao"
#     # ...


# ============================================================
# 你可以在这里注册新的频道
# ============================================================
# CHANNEL_REGISTRY["wechat"] = WechatChannel
# CHANNEL_REGISTRY["telegram"] = TelegramChannel
