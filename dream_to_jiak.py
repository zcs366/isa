#!/usr/bin/env python3
"""
ISA Dreaming → LLM洞察 → jiaK
"""
import sys, json, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from isa import IsaAgent, SignalGraph

CH = f"dream-ins-{int(time.time())}"
graph = SignalGraph(CH, device_id="dream")
agent = IsaAgent("军师-dream", graph=graph)

cards = {
    "isa-wave-mechanics": "ISA波动力学:信号在语义空间中主动传播。波扩散引擎以Jaccard语义距离为度量。",
    "ack-triangle": "ACK三角可靠交付:SessionManager管理通信生命周期。INITIATED→ACKED→RESPONDED→CLOSED。",
    "isa-gateway": "ISA Gateway WebSocket协议:Agent通过register接入Gateway。Token认证、频道隔离。",
    "brain-dreaming": "Brain.dream引擎:离线扫描卡片发现关键词重叠和语义相似关联。双通道匹配。",
    "jsonl-storage": "JSONL不可变追加:所有信号以追加行存储。flock并发保护。永不覆盖。",
    "jiak-memory": "jiaK记忆系统:JSONL追加协议。RECALL时间线、卡片去重注入、语义匹配检索。",
}
for cid, content in cards.items():
    agent.brain.insight(cid, content)

dreams = agent.brain.dream()
print(f"🌙 Brain.dream: {len(dreams)} 组关联")

# LLM洞察
insights = {
    "isa-wave-mechanics↔brain-dreaming": "波扩散引擎与Brain.dream都是语义场中的认知激活机制——前者沿Jaccard距离在Agent间传播信号，后者沿关键词重叠在卡片间发现关联。两者回答了同一问题：认知关联如何在分布式系统中被发现？",
    "brain-dreaming↔jiak-memory": "Dream引擎发现关联，jiak固化关联——主动扫描与不可变记录。本质上是同一认知周期的不同阶段：发现→固化，探索→确认。",
    "jsonl-storage↔jiak-memory": "JSONL追加协议同时支持ISA信号日志和jiak记忆时间线。每一行JSONL既是通信记录，也是记忆痕迹。同一数据结构的两种语义解释。",
}

recall_path = Path.home() / ".hermes" / "jiak" / "RECALL.jsonl"
ts = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')

for d in dreams:
    pk = f"{d['card_a']}↔{d['card_b']}"
    insight = insights.get(pk, "")
    if not insight:
        continue
    entry = {
        "ts": ts,
        "type": "jiak_note",
        "agent": "isa-dreaming",
        "card": d["card_a"],
        "cards": [d["card_a"], d["card_b"]],
        "content": f"[ISA Dreaming] {insight}",
        "summary_short": f"Dream发现: {d['card_a']}↔{d['card_b']} 共享{d.get('shared_keywords', [])}",
    }
    with open(recall_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"📝 RECALL ← {pk}")
    print(f"   💡 {insight}\n")

# 验证
with open(recall_path) as f:
    lines = f.readlines()
isa_lines = [l for l in lines if '"isa-dreaming"' in l]
print(f"━━━ 完成 ━━━")
print(f"   写入jiak RECALL: {len(isa_lines)} 条")
print(f"   RECALL总行数: {len(lines)}")
