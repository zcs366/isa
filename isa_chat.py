#!/usr/bin/env python3
"""
ISA Chat v0.2 — 纯文本聊天界面
零闪烁，直接打字。像IRC一样简单。
"""
import sys, os
sys.path.insert(0, os.path.expanduser("~/projects/isa"))
from isa import *

CH = sys.argv[1] if len(sys.argv) > 1 else "main"
AGENT = os.environ.get("ISA_AGENT", os.environ.get("USER", "anonymous"))
g = SignalGraph(CH, "local")
g.index.rebuild()
a = IsaAgent(AGENT, g)

print(f"\n📡 ISA Chat · 频道: {CH} · 你是: {AGENT}")
print("   直接打字发消息 | /emit 消息 重要性 | /channels | /help | /quit")
print("─" * 60)

# 显示最近消息
sigs = g.retrieve(limit=10)
if sigs:
    for sig in reversed(sigs):
        ts = sig.timestamp[11:19]
        icon = {"message": "💬", "wave": "🌊📬", "wink": "⚡", "resonance": "~"}.get(sig.type, "📨")
        src = sig.source[:12]
        print(f"  {ts} {icon} {src}: {sig.body[:100]}")
else:
    print("  (暂无消息)")
print("─" * 60)

try:
    while True:
        try:
            text = input(f"\n[{AGENT}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出")
            break

        if not text:
            continue

        if text == "/quit":
            break
        elif text == "/channels":
            ch_dir = CHANNELS_DIR
            channels = sorted([d.name for d in ch_dir.iterdir() if d.is_dir()])
            if channels:
                print(f"  频道 ({len(channels)}):")
                for c in channels:
                    store = ChannelStore(c, "local")
                    marker = " ←" if c == CH else ""
                    print(f"    {c} ({store.count()} 信号){marker}")
            else:
                print("  (无频道)")
            continue
        elif text == "/help":
            print("  /emit 消息 重要性 — 波扩散  /wink 目标 信号 — 眨眼")
            print("  /branch 频道名 — 分身      /channels — 频道列表")
            print("  /switch 频道名 — 切换频道   /peers — 附近Agent")
            continue
        elif text.startswith("/switch "):
            new_ch = text[8:].strip()
            CH = new_ch
            g = SignalGraph(CH, "local")
            g.index.rebuild()
            a = IsaAgent(AGENT, g)
            print(f"  → 切换到频道: {CH}")
            sigs = g.retrieve(limit=5)
            for sig in reversed(sigs):
                ts = sig.timestamp[11:19]
                print(f"  {ts} 💬 {sig.source[:12]}: {sig.body[:80]}")
            continue
        elif text == "/peers":
            peers = a.peers()
            if peers:
                for p in sorted(peers):
                    if p != AGENT:
                        dist = a.distance_to(p)
                        bar = "█" * max(1, int((1-dist)*10))
                        print(f"  {p} [{bar}] {dist:.2f}")
            else:
                print("  (附近无Agent)")
            continue
        elif text.startswith("/emit "):
            parts = text[6:].rsplit(" ", 1)
            body = parts[0]
            imp = float(parts[1]) if len(parts) > 1 else 0.5
            ids = a.emit(body, importance=imp)
            print(f"  🌊 发射: 原信号 + {len(ids)-1} 扩散副本")
            g.index.rebuild()
            continue
        elif text.startswith("/wink "):
            parts = text[6:].split(" ", 1)
            if len(parts) == 2:
                a.wink(parts[0], parts[1])
                print(f"  ⚡ 眨眼 → {parts[0]}")
            continue
        elif text.startswith("/branch "):
            new_ch = text[8:].strip()
            from datetime import datetime, timezone
            a.branch(datetime.now(timezone.utc).isoformat(), new_ch)
            print(f"  🦉 分身频道: {new_ch}")
            continue
        else:
            # 普通消息
            sid = a.send("*", text)
            g.index.rebuild()
            print(f"  ✓ 已发送")

except Exception as e:
    print(f"\n错误: {e}")
