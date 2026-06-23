#!/usr/bin/env python3
"""ISA v0.9 端到端 — 认知循环"""
import sys, json, time
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from isa import IsaAgent, SignalGraph, WaveEngine

CH = f"demo-{int(time.time())}"
print(f"🔷 ISA v0.9 E2E  频道: {CH}\n")

graph = SignalGraph(CH, device_id="demo")
a = IsaAgent("军师", graph=graph)
b = IsaAgent("子贡", graph=graph)
print(f"✅ {a.agent_id}  |  {b.agent_id}\n")

# ── 预置子贡记忆（卡片+关键词自动提取）──
cards = {
    "isa-wave-mechanics": "ISA波动力学:信号在语义空间中主动传播。波扩散引擎以Jaccard语义距离为度量。",
    "ack-triangle": "ACK三角可靠交付:INITIATED→ACKED→RESPONDED→CLOSED。SLA超时重试3次。",
    "wave-decay": "波扩散系数DEFAULT_WAVE_DECAY=0.7控制信号衰减。系数越接近1传播越远。Jaccard距离决定初始振幅。",
}
for cid, content in cards.items():
    b.brain.insight(cid, content)
    print(f"📝 {cid}: {b.brain._extract_keywords(content)}")

# ── 军师发送 ──
print()
msg = "波扩散系数如何影响通信范围？和Jaccard距离的关系？"
session_id = a.send_reliable(target="子贡", body=msg)
graph.index.rebuild()
print(f"📤 军师 → 子贡: \"{msg}\"")
print(f"🔖 Session: {session_id[:16]}...\n")

# ── 子贡接收 → Brain认知 ──
received = graph.retrieve(target="子贡", limit=5)
for sig in received[-1:]:
    kw = b.brain._extract_keywords(sig.body)
    print(f"📥 子贡收到: \"{sig.body}\"")
    print(f"   关键词: {kw}")
    matches = b.brain.ingest_signal(asdict(sig))
    print(f"   🧠 Brain匹配 {len(matches)} 张卡片:")
    for m in matches:
        print(f"      📇 {m.get('title', '?')} (score={m.get('score',0.0):.2f})")

# ── Brain.dream ──
print()
dream = b.brain.dream()
print(f"🌙 Brain.dream: {len(dream)} 组关联")
for a_id, b_id, overlap in dream:
    print(f"   {a_id} ↔ {b_id} ({overlap}个关键词)")

# ── 统计 ──
print()
print(f"📊 JSONL: {graph.store.count()}条Signal")
print(f"📊 Brain: {json.dumps(b.brain._stats)}")
with open(graph.store.events_path) as f:
    lines = f.readlines()
print(f"📄 events.jsonl: {len(lines)}行 (只追加)")
for line in lines[-3:]:
    s = json.loads(line)
    print(f"   [{s['type']:8s}] {s.get('source','?'):8s} → {s.get('target','?'):8s}: {s.get('body','')[:50]}")
print("\n━━━ ✅ ISA v0.9 认知循环完整闭环 ━━━")
