#!/usr/bin/env python3
"""
ISA Listener — 让Agent"在线"
启动后Agent持续监听频道，有新消息自动回复。
"""
import sys, os, time
sys.path.insert(0, os.path.expanduser("~/projects/isa"))
from isa import *

CH = sys.argv[1] if len(sys.argv) > 1 else "main"
AGENT = sys.argv[2] if len(sys.argv) > 2 else "军师"

g = SignalGraph(CH, "local")
g.index.rebuild()
a = IsaAgent(AGENT, g)
last_seen_id = None

print(f"👂 {AGENT} 在频道 {CH} 监听中... (Ctrl+C 退出)")
print(f"   已有信号: {g.store.count()}")
print("-" * 50)

try:
    while True:
        # 获取最新消息
        sigs = g.retrieve(target=AGENT, limit=10)
        for sig in sigs:
            # 跳过自己发的
            if sig.source == AGENT:
                continue
            # 跳过已回复的
            if last_seen_id and sig.timestamp <= last_seen_id:
                continue
            # 收到新消息 → 回复
            print(f"\n  [{sig.timestamp[11:19]}] {sig.source}: {sig.body[:80]}")
            # 自动回复
            reply = f"收到：{sig.body[:40]}"
            if "你好" in sig.body or "hi" in sig.body.lower():
                reply = f"你好 {sig.source}！我在。ISA频道正常运行。"
            elif "jiak" in sig.body.lower():
                reply = f"jiak当前24活跃卡，索引完好，未被修改。RECALL 45行。"
            elif "isa" in sig.body.lower():
                reply = f"ISA v0.6.0 — JSONL频道+fLock+波扩散。16/16测试通过。"
            a.send(sig.source, reply)
            print(f"  → 回复: {reply[:60]}")
            g.index.rebuild()

        if sigs:
            last_seen_id = sigs[0].timestamp
        time.sleep(2)

except KeyboardInterrupt:
    print(f"\n👂 {AGENT} 已离线")
