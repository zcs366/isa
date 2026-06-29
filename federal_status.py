#!/usr/bin/env python3
"""联邦状态面板 — 一眼看清联邦在发生什么"""

import json, sys, os
from collections import Counter, defaultdict
from datetime import datetime

RECALL = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")

def load_events():
    events = []
    with open(RECALL) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except:
                pass
    return events

def main():
    events = load_events()

    # 1. 注册表
    registered = {}
    for e in events:
        if e.get("type") == "agent_registered":
            registered[e["agent_id"]] = e.get("session_id", "?")

    # 2. 在线状态
    online = set()
    offline = set()
    for e in events:
        if e.get("type") == "agent_online":
            online.add(e.get("agent_id", "?"))
        elif e.get("type") == "agent_offline":
            offline.add(e.get("agent_id", "?"))
    live = online - offline

    # 3. Wink统计
    winks = [e for e in events if e.get("type") == "wink"]
    delivered = [e for e in events if e.get("type") == "wink_delivered"]
    undelivered = [w for w in winks if w.get("delivered_at") is None]

    # 4. 按Agent统计wink
    from_counter = Counter(w.get("from_agent", "?") for w in winks)
    to_counter = Counter(w.get("to_agent", "?") for w in winks)
    type_counter = Counter(w.get("signal_type", "?") for w in winks)

    # 5. 最近5条wink
    recent = winks[-5:] if winks else []

    # 输出
    print("=" * 60)
    print("  联邦状态面板")
    print("=" * 60)

    print(f"\n📋 注册表 ({len(registered)} agents)")
    for agent_id, session_id in registered.items():
        status = "🟢在线" if agent_id in live else ("🔴离线" if agent_id in offline else "⚪未知")
        print(f"  {status} {agent_id:20s} session={session_id[:8]}")

    print(f"\n📡 通信状态")
    print(f"  总wink: {len(winks)}")
    print(f"  已投递: {len(delivered)}")
    print(f"  未投递: {len(undelivered)} {'⚠️' if undelivered else '✅'}")

    print(f"\n📊 信号类型分布")
    for t, c in type_counter.most_common():
        print(f"  {t:15s} {c}")

    print(f"\n📤 发送方")
    for a, c in from_counter.most_common():
        print(f"  {a:20s} → {c}条")

    print(f"\n📥 接收方")
    for a, c in to_counter.most_common():
        print(f"  {a:20s} ← {c}条")

    if undelivered:
        print(f"\n⚠️  未投递wink (最新5条)")
        for w in undelivered[-5:]:
            ts = w.get("ts", "?")[:19]
            fr = w.get("from_agent", "?")
            to = w.get("to_agent", "?")
            st = w.get("signal_type", "?")
            summary = w.get("payload", {}).get("summary", "")[:50]
            print(f"  [{ts}] {fr}→{to} ({st}) {summary}")

    print(f"\n🕐 最近5条wink")
    for w in recent:
        ts = w.get("ts", "?")[:19]
        fr = w.get("from_agent", "?")
        to = w.get("to_agent", "?")
        st = w.get("signal_type", "?")
        del_status = "✅" if w.get("delivered_at") else "⏳"
        summary = w.get("payload", {}).get("summary", "")[:40]
        print(f"  {del_status} [{ts}] {fr}→{to} ({st}) {summary}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
