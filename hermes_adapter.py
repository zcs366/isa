#!/usr/bin/env python3
"""
Hermes ISA Adapter — 让军师（Hermes Agent）接入ISA语义场
============================================================

军师的语义指纹：
  关键词从Iam原则和SOUL.md中提取——代表了军师的"在意什么"。
  这些关键词决定了军师在语义场中的位置和共振范围。

三种模式：
  1. init —— 注册军师到ISA语义场（写入presence信号）
  2. daemon —— 后台常驻，WebSocket连接Gateway，收消息→mailbox，发消息←outbox
  3. one-shot —— 单次发送/接收（Hermes通过terminal调用）

Mailbox机制：
  ~/.hermes/isa/mailbox/isa_in.jsonl  ← Gateway推送的消息（daemon写入）
  ~/.hermes/isa/mailbox/isa_out.jsonl → 军师要发的消息（Hermes agent写入，daemon读取后发送）

Hermes Agent使用方式：
  # 初始化（首次）
  python hermes_adapter.py init

  # 启动daemon（后台）
  python hermes_adapter.py daemon &

  # 发送消息到ISA
  python hermes_adapter.py send "关于语义压缩的新想法..."

  # 查看收件箱
  python hermes_adapter.py poll
"""

import argparse
import asyncio
import json
import os
import sys
import time
import signal
from pathlib import Path

# ISA Core 导入
sys.path.insert(0, str(Path(__file__).parent))
from isa import (
    Signal, SignalGraph, DEFAULT_CHANNEL, CHANNELS_DIR,
    WaveEngine, IsaAgent,
)

# 军师身份
HERMES_AGENT_ID = "军师"  # 老搭档给我取的名字
HERMES_CHANNEL = "main"

# 军师的语义指纹——从Iam原则和SOUL中提取的核心关键词
HERMES_KEYWORDS = {
    "AI": 0.95,
    "Agent": 0.9,
    "记忆": 0.9,
    "语义": 0.85,
    "通信": 0.85,
    "本体": 0.8,
    "原则": 0.8,
    "铁律": 0.8,
    "架构": 0.75,
    "波扩散": 0.75,
    "共振": 0.75,
    "哲学": 0.7,
    "文学": 0.65,
    "翻译": 0.6,
    "创作": 0.6,
    "研究": 0.7,
    "安全": 0.65,
    "身份": 0.75,
    "连续性": 0.7,
    "不可变": 0.8,
    "追加": 0.7,
    "合议": 0.65,
    "审查": 0.6,
    "工程": 0.7,
    "产品": 0.65,
}

# Mailbox路径
MAILBOX_DIR = Path.home() / ".hermes" / "isa" / "mailbox"
MAILBOX_DIR.mkdir(parents=True, exist_ok=True)
ISA_IN = MAILBOX_DIR / "isa_in.jsonl"   # daemon写入，Hermes读取
ISA_OUT = MAILBOX_DIR / "isa_out.jsonl"  # Hermes写入，daemon读取后发送
ISA_SENT = MAILBOX_DIR / "isa_sent.jsonl" # 已发送记录（不可变追加）


# ═══════════════════════════════════════════════════════════════
# 初始化——在ISA语义场中注册军师
# ═══════════════════════════════════════════════════════════════

def init():
    """首次初始化：在ISA中写入军师的presence信号。"""
    graph = SignalGraph(HERMES_CHANNEL, device_id="hermes")

    # 写入身份声明
    signal = Signal(
        type="presence",
        source=HERMES_AGENT_ID,
        target="*",
        body="军师已接入ISA语义场",
        meta={
            "keywords": HERMES_KEYWORDS,
            "role": "军师祭酒 — 人生助理与专业顾问",
            "platform": "Hermes Agent",
            "version": "0.1.0",
        },
    )
    sid = graph.ingest(signal)
    graph.index.rebuild()

    print(f"[军师] ✅ 已注册到ISA语义场")
    print(f"[军师]    信号ID: {sid}")
    print(f"[军师]    频道: #{HERMES_CHANNEL}")
    print(f"[军师]    关键词: {len(HERMES_KEYWORDS)}个")
    print(f"[军师]    存储: {graph.store.events_path}")

    return sid


# ═══════════════════════════════════════════════════════════════
# 发送——军师向ISA发送消息
# ═══════════════════════════════════════════════════════════════

def send_message(body: str, target: str = "*", importance: float = 0.5):
    """向ISA发送一条消息（仅写outbox，由daemon→Gateway→Core单路径写入）。

    不再直接写Core——那样会与Gateway的ingest重复。
    daemon会读取outbox并通过WebSocket发送到Gateway，
    Gateway负责写入Core+波扩散+广播。
    """
    # 只写outbox——让daemon→Gateway单路径写入Core
    msg = {
        "type": "message",
        "target": target,
        "body": body,
        "importance": importance,
    }
    with open(ISA_OUT, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    # 记录到已发送
    with open(ISA_SENT, "a") as f:
        f.write(json.dumps({
            "body": body[:200],
            "target": target,
            "importance": importance,
            "timestamp": time.time(),
            "via": "outbox→daemon→gateway",
        }, ensure_ascii=False) + "\n")

    return None, 0  # signal_id由Gateway分配


# ═══════════════════════════════════════════════════════════════
# 接收——查看发给军师的消息
# ═══════════════════════════════════════════════════════════════

def poll_messages(limit: int = 20) -> list[dict]:
    """查看ISA中发给军师的消息（从Core读取）。"""
    graph = SignalGraph(HERMES_CHANNEL, device_id="hermes")

    # 从Core检索
    signals = graph.retrieve(target=HERMES_AGENT_ID, limit=limit)
    # 也搜共振消息
    signals += graph.retrieve(target="resonance", limit=limit // 2)
    # 搜广播
    signals += graph.retrieve(target="*", limit=limit // 2)

    # 去重 + 排序（按时间倒序）
    seen = set()
    unique = []
    for s in signals:
        if s.id not in seen and s.source != HERMES_AGENT_ID:
            seen.add(s.id)
            unique.append(s)
    unique.sort(key=lambda s: s.timestamp, reverse=True)

    return [
        {
            "id": s.id,
            "type": s.type,
            "source": s.source,
            "body": s.body,
            "timestamp": s.timestamp,
            "wave": s.meta.get("propagated", False),
            "importance": s.meta.get("importance", 0.5),
            "semantic_distance": s.meta.get("semantic_distance"),
        }
        for s in unique[:limit]
    ]


# ═══════════════════════════════════════════════════════════════
# Daemon——后台常驻，通过WebSocket连接Gateway
# ═══════════════════════════════════════════════════════════════

async def daemon_async(gateway_url: str = "ws://localhost:8765"):
    """后台Daemon——WebSocket连接Gateway，自动重连。

    连接状态机：disconnected → connecting → connected → disconnected → ...
    每次断连后等待3秒重试，无限循环。
    """
    try:
        import websockets
    except ImportError:
        print("[军师] ❌ 需要websockets库: pip install websockets")
        sys.exit(1)

    url = f"{gateway_url}/isa/channel/{HERMES_CHANNEL}"
    reconnect_delay = 3  # 秒

    while True:
        try:
            print(f"[军师] 🔌 连接Gateway: {url}")
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                # 注册
                await ws.send(json.dumps({
                    "type": "register",
                    "agent_id": HERMES_AGENT_ID,
                    "channel": HERMES_CHANNEL,
                    "keywords": HERMES_KEYWORDS,
                }, ensure_ascii=False))

                reply = json.loads(await ws.recv())
                if reply.get("type") != "registered":
                    print(f"[军师] ❌ 注册失败: {reply}")
                    await asyncio.sleep(reconnect_delay)
                    continue

                print(f"[军师] ✅ 已连接 · {reply.get('peer_count', 0)} Agent在线")

                # 双工循环：收ISA消息 + 读outbox
                async def receive_loop():
                    """接收Gateway推送 → 写入mailbox in"""
                    try:
                        async for raw in ws:
                            try:
                                msg = json.loads(raw)
                                with open(ISA_IN, "a") as f:
                                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
                                if msg.get("type") in ("message", "resonate", "wink"):
                                    source = msg.get("source", "?")
                                    body = msg.get("body", "")[:60]
                                    print(f"[军师] 📩 {source}: {body}")
                            except Exception as e:
                                print(f"[军师] ⚠ 接收错误: {e}")
                    except Exception:
                        pass  # 连接断开，外层while会重连

                async def send_loop():
                    """读outbox → 发送到Gateway"""
                    last_pos = 0
                    try:
                        while True:
                            await asyncio.sleep(0.5)
                            if ISA_OUT.exists():
                                with open(ISA_OUT, "rb") as f:   # 二进制模式，避免文本缓冲导致tell()不准
                                    f.seek(last_pos)
                                    for line in f:
                                        line = line.decode("utf-8").strip()
                                        if not line:
                                            continue
                                        try:
                                            msg = json.loads(line)
                                            await ws.send(json.dumps(msg, ensure_ascii=False))
                                            print(f"[军师] 📤 已发送: {msg.get('body', '')[:60]}")
                                        except json.JSONDecodeError:
                                            pass
                                    last_pos = f.tell()  # 二进制模式tell()准确
                    except Exception:
                        pass  # 连接断开

                await asyncio.gather(receive_loop(), send_loop())

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.InvalidURI,
                websockets.exceptions.InvalidHandshake,
                OSError,
                asyncio.TimeoutError) as e:
            print(f"[军师] ⚠ 连接断开: {type(e).__name__}")
        except Exception as e:
            print(f"[军师] ⚠ 未知错误: {type(e).__name__}: {e}")

        print(f"[军师] 🔄 {reconnect_delay}秒后重连...")
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 1.5, 30)  # 退避，最多30秒


def daemon(gateway_url: str = "ws://localhost:8765"):
    """同步入口。"""
    asyncio.run(daemon_async(gateway_url))


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Hermes ISA Adapter — 军师接入ISA语义场",
    )
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="初始化——在ISA中注册军师")

    # send
    p_send = sub.add_parser("send", help="发送消息到ISA")
    p_send.add_argument("body", help="消息内容")
    p_send.add_argument("--target", default="*", help="目标Agent (默认: 广播)")
    p_send.add_argument("--importance", type=float, default=0.5,
                        help="重要性 0-1 (≥0.4触发波扩散)")

    # poll
    p_poll = sub.add_parser("poll", help="查看发给军师的消息")
    p_poll.add_argument("--limit", type=int, default=20)

    # daemon
    p_daemon = sub.add_parser("daemon", help="后台常驻——WebSocket连接Gateway")
    p_daemon.add_argument("--gateway", default="ws://localhost:8765")

    # mailbox
    p_mailbox = sub.add_parser("mailbox", help="查看mailbox中的消息")
    p_mailbox.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()

    if args.command == "init":
        init()

    elif args.command == "send":
        sid, wave_count = send_message(args.body, args.target, args.importance)
        print(f"[军师] 📤 已发送 → {args.target}")
        print(f"       途经: outbox → daemon → Gateway → Core")

    elif args.command == "poll":
        msgs = poll_messages(args.limit)
        if not msgs:
            print("[军师] 📭 收件箱为空")
        else:
            print(f"[军师] 📬 {len(msgs)} 条消息:")
            for m in msgs:
                wave_icon = "🌊" if m["wave"] else " "
                dist_str = f" 距离:{m['semantic_distance']:.2f}" if m.get("semantic_distance") else ""
                print(f"  {wave_icon} [{m['type']}] {m['source']}{dist_str}: {m['body'][:100]}")

    elif args.command == "mailbox":
        # 读取mailbox in
        if ISA_IN.exists():
            lines = []
            with open(ISA_IN, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        lines.append(line)
            recent = lines[-args.limit:]
            print(f"[军师] 📬 Mailbox ({len(recent)}/{len(lines)}):")
            for line in recent:
                try:
                    m = json.loads(line)
                    src = m.get("source", "?")
                    body = m.get("body", "")[:100]
                    print(f"  [{m.get('type', '?')}] {src}: {body}")
                except json.JSONDecodeError:
                    print(f"  [解析错误] {line[:100]}")
        else:
            print("[军师] 📭 Mailbox为空")

    elif args.command == "daemon":
        daemon(args.gateway)

    else:
        parser.print_help()
