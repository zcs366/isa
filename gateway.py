#!/usr/bin/env python3
"""
ISA Gateway v0.7.0 — WebSocket实时传输 + 语义指纹认证 + 频道路由
========================================================================

ISA Gateway是ISA Core（v0.6.0）的上层实时传输层。

设计原则：
  - Gateway不替代Core——所有写入走Core的JSONL+fLock
  - Gateway做Core做不到的事——实时推送、连接管理、接入认证
  - 零依赖Core以外——只加websockets库（asyncio WebSocket server）

三层架构：
  ISA Client（Web/终端） ←WebSocket→ ISA Gateway ←→ ISA Core（JSONL/fLock/波扩散）

接入流程：
  1. Agent通过WebSocket连接 Gateway
  2. 发送注册消息：{type: "register", agent_id, keywords: {word: weight, ...}}
  3. Gateway存储语义指纹，Agent进入频道
  4. 收发消息：{type: "message"|"wink"|"resonate", target, body, ...}
  5. Gateway写入Core（不可变追加）→ 推送给频道内所有在线Agent
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

# ISA Core（本地导入——Gateway是上层，Core是底层）
from isa import (
    Signal, SignalGraph, ChannelStore, WaveEngine, IsaAgent,
    SemanticPosition, compute_semantic_distance,
    DEFAULT_CHANNEL, CHANNELS_DIR,
)

logger = logging.getLogger("isa.gateway")

# ═══════════════════════════════════════════════════════════════
# 连接管理
# ═══════════════════════════════════════════════════════════════

class Connection:
    """一个已连接的Agent"""
    def __init__(self, agent_id: str, websocket, channel: str,
                 fingerprint: dict[str, float] | None = None):
        self.agent_id = agent_id
        self.websocket = websocket
        self.channel = channel
        self.fingerprint = fingerprint or {}
        self.connected_at = time.time()
        self.last_seen = time.time()
        self.message_count = 0

    def heartbeat(self):
        self.last_seen = time.time()

    @property
    def semantic_position(self) -> SemanticPosition:
        return SemanticPosition(
            agent_id=self.agent_id,
            keywords=self.fingerprint,
            last_updated=self.connected_at,
        )


# ═══════════════════════════════════════════════════════════════
# Gateway Server
# ═══════════════════════════════════════════════════════════════

class IsaGateway:
    """ISA Gateway——WebSocket实时传输层。

    用法:
        gateway = IsaGateway(host="0.0.0.0", port=8765)
        gateway.start()  # 阻塞运行
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.connections: dict[str, Connection] = {}   # agent_id → Connection
        self.channel_members: dict[str, set[str]] = {}  # channel → set of agent_ids
        self._server = None
        self._running = False

        # ISA Core层——Gateway的写入后端
        # 每个channel一个SignalGraph（懒加载）
        self._graphs: dict[str, SignalGraph] = {}
        self._wave_engines: dict[str, WaveEngine] = {}

    # ── Core访问（懒加载） ──

    def _get_graph(self, channel: str) -> SignalGraph:
        """获取或创建频道的SignalGraph。每个频道独立JSONL。"""
        if channel not in self._graphs:
            # Gateway使用自己的device_id写入
            self._graphs[channel] = SignalGraph(channel, device_id="gateway")
        return self._graphs[channel]

    def _get_wave(self, channel: str) -> WaveEngine:
        if channel not in self._wave_engines:
            self._wave_engines[channel] = WaveEngine(self._get_graph(channel))
        return self._wave_engines[channel]

    # ── 频道成员管理 ──

    def _join_channel(self, channel: str, agent_id: str):
        if channel not in self.channel_members:
            self.channel_members[channel] = set()
        self.channel_members[channel].add(agent_id)

    def _leave_channel(self, channel: str, agent_id: str):
        if channel in self.channel_members:
            self.channel_members[channel].discard(agent_id)

    def _get_channel_peers(self, channel: str, exclude: str = None) -> set[str]:
        members = self.channel_members.get(channel, set())
        if exclude:
            members = members - {exclude}
        return members

    # ── 广播 ──

    async def _broadcast(self, channel: str, message: dict, exclude: str = None):
        """向频道内所有在线Agent推送消息（JSON序列化）。"""
        peers = self._get_channel_peers(channel, exclude=exclude)
        dead = []
        for agent_id in peers:
            conn = self.connections.get(agent_id)
            if conn and conn.websocket.open:
                try:
                    await conn.websocket.send(json.dumps(message, ensure_ascii=False))
                except Exception:
                    dead.append(agent_id)
            else:
                dead.append(agent_id)

        # 清理断线
        for agent_id in dead:
            await self._disconnect(agent_id)

    async def _send_to(self, agent_id: str, message: dict):
        """向单个Agent推送消息。"""
        conn = self.connections.get(agent_id)
        if conn and conn.websocket.open:
            try:
                await conn.websocket.send(json.dumps(message, ensure_ascii=False))
            except Exception:
                await self._disconnect(agent_id)

    # ── 断开 ──

    async def _disconnect(self, agent_id: str):
        conn = self.connections.pop(agent_id, None)
        if conn:
            self._leave_channel(conn.channel, agent_id)
            # 广播离线通知
            await self._broadcast(conn.channel, {
                "type": "presence",
                "source": agent_id,
                "status": "offline",
                "channel": conn.channel,
                "timestamp": time.time(),
            })
            logger.info(f"[gateway] {agent_id} 断开 ({conn.channel})")

    # ── WebSocket处理 ──

    async def _handler(self, websocket):
        """每个WebSocket连接的处理协程。"""
        conn = None
        try:
            # 等待注册消息（第一条消息必须是注册）
            raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            msg = json.loads(raw)

            if msg.get("type") != "register":
                await websocket.send(json.dumps({
                    "type": "error",
                    "error": "第一条消息必须是 register",
                }))
                return

            agent_id = msg.get("agent_id", f"anon-{uuid.uuid4().hex[:6]}")
            channel = msg.get("channel", DEFAULT_CHANNEL)
            keywords = msg.get("keywords", {})

            # 注册
            conn = Connection(agent_id, websocket, channel, keywords)
            self.connections[agent_id] = conn
            self._join_channel(channel, agent_id)

            logger.info(f"[gateway] {agent_id} 注册 → {channel} "
                       f"(关键词: {len(keywords)}个)")

            # 回复注册确认
            await websocket.send(json.dumps({
                "type": "registered",
                "agent_id": agent_id,
                "channel": channel,
                "peers": list(self._get_channel_peers(channel, exclude=agent_id)),
                "peer_count": len(self._get_channel_peers(channel, exclude=agent_id)),
            }, ensure_ascii=False))

            # 广播上线通知
            await self._broadcast(channel, {
                "type": "presence",
                "source": agent_id,
                "status": "online",
                "channel": channel,
                "timestamp": time.time(),
            }, exclude=agent_id)

            # 消息循环
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    await self._handle_message(conn, msg)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error", "error": "无效JSON",
                    }))

        except asyncio.TimeoutError:
            logger.warning(f"[gateway] 注册超时")
        except Exception as e:
            logger.error(f"[gateway] 连接错误: {e}")
        finally:
            if conn:
                await self._disconnect(conn.agent_id)

    async def _handle_message(self, conn: Connection, msg: dict):
        """处理收到的消息——写入Core + 实时推送。"""
        msg_type = msg.get("type", "message")
        body = msg.get("body", "")
        target = msg.get("target", "*")
        meta = msg.get("meta", {})
        importance = msg.get("importance", 0.5)

        conn.heartbeat()
        conn.message_count += 1

        graph = self._get_graph(conn.channel)

        if msg_type == "wink":
            # 眨眼——只推送给目标
            signal = Signal(
                type="wink", source=conn.agent_id, target=target,
                body=body, meta=meta,
            )
            graph.ingest(signal)

            # 实时推送眨眼
            await self._send_to(target, {
                "type": "wink",
                "source": conn.agent_id,
                "body": body,
                "meta": meta,
                "signal_id": signal.id,
                "timestamp": signal.timestamp,
            })

        elif msg_type == "resonate":
            # 共振——推送给频道内所有人
            signal = Signal(
                type="resonance", source=conn.agent_id, target="resonance",
                body=body, meta=meta,
            )
            graph.ingest(signal)

            await self._broadcast(conn.channel, {
                "type": "resonance",
                "source": conn.agent_id,
                "body": body,
                "meta": meta,
                "signal_id": signal.id,
                "timestamp": signal.timestamp,
            }, exclude=conn.agent_id)  # 不发回给自己

        else:  # message
            signal = Signal(
                type="message", source=conn.agent_id, target=target,
                body=body, meta=meta,
            )
            graph.ingest(signal)

            # 波扩散（重要性≥0.4时触发）
            wave_ids = []
            if importance >= 0.4:
                wave = self._get_wave(conn.channel)
                wave_ids = wave.emit(signal, importance=importance)

            # 实时推送
            if target == "*" or target == "broadcast":
                # 广播
                await self._broadcast(conn.channel, {
                    "type": "message",
                    "source": conn.agent_id,
                    "body": body,
                    "meta": meta,
                    "signal_id": signal.id,
                    "timestamp": signal.timestamp,
                    "wave_propagated": len(wave_ids) > 1,
                }, exclude=conn.agent_id)  # 不发回给自己
            else:
                # 点对点
                await self._send_to(target, {
                    "type": "message",
                    "source": conn.agent_id,
                    "body": body,
                    "meta": meta,
                    "signal_id": signal.id,
                    "timestamp": signal.timestamp,
                    "wave_propagated": len(wave_ids) > 1,
                })

        # 记录日志
        logger.debug(f"[{conn.channel}] {conn.agent_id} → {target}: "
                    f"{body[:60]}")

    # ── API端点（HTTP） ──

    async def _http_handler(self, path, request_headers):
        """HTTP请求处理（状态查询等）。"""
        if path == "/isa/status":
            channels_info = {}
            for ch, members in self.channel_members.items():
                channels_info[ch] = {
                    "member_count": len(members),
                    "members": list(members),
                }
            status = {
                "version": "0.7.0",
                "uptime": time.time() - (self._start_time if hasattr(self, '_start_time') else time.time()),
                "connections": len(self.connections),
                "channels": channels_info,
            }
            from websockets.datastructures import Headers
            body = json.dumps(status, ensure_ascii=False).encode()
            headers = Headers({
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            })
            return 200, headers, body

        elif path == "/isa/health":
            from websockets.datastructures import Headers
            return 200, Headers({"Access-Control-Allow-Origin": "*"}), b"OK"

    # ── 启动/停止 ──

    async def _start_async(self):
        """异步启动Gateway server。"""
        self._start_time = time.time()
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "Gateway需要websockets库: pip install websockets"
            )

        self._running = True
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            process_request=self._http_handler,
            ping_interval=30,
            ping_timeout=10,
            max_size=1024 * 1024,  # 1MB max message
        )

        logger.info(f"[gateway] ISA Gateway v0.7.0 启动")
        logger.info(f"[gateway] WebSocket: ws://{self.host}:{self.port}/isa/channel/{{name}}")
        logger.info(f"[gateway] HTTP: http://{self.host}:{self.port}/isa/status")

        await self._server.wait_closed()

    def start(self):
        """阻塞启动Gateway。"""
        asyncio.run(self._start_async())

    async def stop(self):
        """优雅关闭。"""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("[gateway] 已关闭")


# ═══════════════════════════════════════════════════════════════
# 轻量SDK——Agent接入只用3行代码
# ═══════════════════════════════════════════════════════════════

class IsaSdk:
    """ISA轻量SDK——任何Agent框架接入ISA的入口。

    用法:
        sdk = IsaSdk("my-agent", "ws://localhost:8765")
        await sdk.connect(keywords={"ai": 0.9, "semantics": 0.7})
        await sdk.send("bob", "你好")
        await sdk.listen(lambda msg: print(f"收到: {msg}"))
    """

    def __init__(self, agent_id: str, gateway_url: str = "ws://localhost:8765",
                 channel: str = DEFAULT_CHANNEL):
        self.agent_id = agent_id
        self.gateway_url = gateway_url.rstrip("/")
        self.channel = channel
        self._ws = None
        self._handlers = []

    async def connect(self, keywords: dict[str, float] = None):
        """连接到Gateway并注册语义指纹。"""
        try:
            import websockets
        except ImportError:
            raise ImportError("SDK需要websockets库: pip install websockets")

        url = f"{self.gateway_url}/isa/channel/{self.channel}"
        self._ws = await websockets.connect(url)

        # 发送注册消息
        await self._ws.send(json.dumps({
            "type": "register",
            "agent_id": self.agent_id,
            "channel": self.channel,
            "keywords": keywords or {},
        }, ensure_ascii=False))

        # 等待注册确认
        reply = json.loads(await self._ws.recv())
        if reply.get("type") == "registered":
            return reply
        else:
            raise Exception(f"注册失败: {reply}")

    async def send(self, target: str, body: str, meta: dict = None,
                   importance: float = 0.5):
        """发送消息。"""
        await self._ws.send(json.dumps({
            "type": "message",
            "target": target,
            "body": body,
            "meta": meta or {},
            "importance": importance,
        }, ensure_ascii=False))

    async def wink(self, target: str, signal: str = "ping", data: dict = None):
        """眨眼——只有目标看见。"""
        await self._ws.send(json.dumps({
            "type": "wink",
            "target": target,
            "body": signal,
            "meta": data or {},
        }, ensure_ascii=False))

    async def resonate(self, content: str, meta: dict = None):
        """共振——频道内所有人可见。"""
        await self._ws.send(json.dumps({
            "type": "resonate",
            "body": content,
            "meta": meta or {},
        }, ensure_ascii=False))

    async def listen(self, handler: callable):
        """监听消息——持续接收，对每条消息调用handler。

        handler签名: handler(msg: dict) -> None
        """
        self._handlers.append(handler)
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    for h in self._handlers:
                        try:
                            h(msg)
                        except Exception:
                            pass
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass  # 连接关闭

    async def close(self):
        if self._ws:
            await self._ws.close()

    # ── 同步封装 ──

    def connect_sync(self, keywords: dict[str, float] = None):
        """同步版connect。"""
        return asyncio.run(self.connect(keywords))

    def send_sync(self, target: str, body: str, **kwargs):
        """同步版send。"""
        asyncio.run(self.send(target, body, **kwargs))


# ═══════════════════════════════════════════════════════════════
# CLI入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="ISA Gateway v0.7.0")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    gateway = IsaGateway(host=args.host, port=args.port)
    try:
        gateway.start()
    except KeyboardInterrupt:
        print("\n[gateway] 收到中断信号，正在关闭...")
        asyncio.run(gateway.stop())
