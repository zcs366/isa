#!/usr/bin/env python3
"""
ISA v0.9.2 多Agent并发验证
===========================
验证:
  1. 3个Agent同时连接Gateway
  2. 通过共享SignalGraph并发通信
  3. 每个Agent的Brain独立处理信号
  4. JSONL无损坏
"""
import sys, os, json, time, threading
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from isa import IsaAgent, SignalGraph, Signal

CHANNEL = f"concurrent-{int(time.time())}"
N_AGENTS = 3
N_MESSAGES = 10  # 每个Agent发几条

print(f"🔷 ISA 多Agent并发验证")
print(f"   频道: {CHANNEL}")
print(f"   Agent数: {N_AGENTS}")
print(f"   消息数/Agent: {N_MESSAGES}")
print()

# ── 共享SignalGraph ──
graph = SignalGraph(CHANNEL, device_id="concurrent-test")
print(f"   📁 {graph.store.events_path}")
print()

# ── 创建3个Agent ──
agents = [
    IsaAgent("军师", graph=graph),
    IsaAgent("子贡", graph=graph),
    IsaAgent("包拯", graph=graph),
]
for a in agents:
    print(f"   ✅ {a.agent_id} — Brain: {a.brain.brain_dir}")
print()

# ── 预置各自记忆 ──
agents[0].brain.insight("isa-strategy", "ISA架构设计:认知层与治理层分离。军师负责ISA认知层(波扩散/Brain/Dreaming/Gateway)。权力分离不可越界。")
agents[1].brain.insight("resource-allocation", "资源调度策略:多Agent并发时的信号路由和负载分配。基于语义距离的优先级路由。")
agents[2].brain.insight("audit-chain", "审计链:root sigil定义cap_policy→IO-S执行资源操作→包拯独立审计cap_policy未篡改。不可变JSONL是审计基座。")
for i, a in enumerate(agents):
    a.brain.insight(f"agent-{a.agent_id}", f"{a.agent_id}的职责定义和边界")
print(f"   预置记忆: 每人2张卡片")
print()

# ── 并发消息测试 ──
print("━━━ 并发消息发送 ━━━")
errors = []
lock = threading.Lock()
results = {"sent": 0, "sessions": 0}

def agent_sender(agent, target, n):
    """Agent发送n条消息"""
    for i in range(n):
        try:
            body = f"[{agent.agent_id}] 测试消息#{i+1}: ISA波动力学中的语义距离传播.{'编号'*(i%5+1)}"
            agent.send(target, body)
            with lock:
                results["sent"] += 1
        except Exception as e:
            with lock:
                errors.append(f"{agent.agent_id} msg#{i}: {e}")

threads = []
# 每个Agent发N_MESSAGES条广播
for a in agents:
    t = threading.Thread(target=agent_sender, args=(a, "*", N_MESSAGES))
    threads.append(t)

# 再增加点对点发送
for i, a in enumerate(agents):
    target = agents[(i+1) % N_AGENTS].agent_id
    for j in range(3):
        body = f"[{a.agent_id}] 点对点→{target}: 关于ISA架构的#{j+1}个问题"
        a.send(target, body)
        results["sent"] += 1

# 并发启动
for t in threads:
    t.start()
for t in threads:
    t.join(timeout=15)

# 强制重建索引
graph.index.rebuild()

print(f"   已发送: {results['sent']} 条")
print(f"   错误: {len(errors)}")
for e in errors[:5]:
    print(f"      ❌ {e}")
print()

# ── 验证：每个Agent的Brain是否能检索到自己的消息 ──
print("━━━ Brain独立认知验证 ━━━")
for agent in agents:
    # Agent检索发给自己的信号
    signals = graph.retrieve(target=agent.agent_id, limit=5)
    print(f"   🔍 {agent.agent_id}: 检索到 {len(signals)} 条点对点信号")
    
    # Agent处理信号
    for sig in signals:
        matches = agent.brain.ingest_signal(asdict(sig))
        if matches:
            print(f"      🧠 匹配 {len(matches)} 张卡片")
    
    # Brain.dream
    dreams = agent.brain.dream()
    if dreams:
        print(f"      🌙 发现 {len(dreams)} 组关联:")
        for d in dreams:
            print(f"         {d['card_a']} ↔ {d['card_b']}: {d.get('shared_keywords', [])}")

print()

# ── 验证JSONL完整性 ──
print("━━━ JSONL完整性验证 ━━━")
with open(graph.store.events_path) as f:
    lines = f.readlines()
print(f"   总行数: {len(lines)}")
corrupt = 0
for i, line in enumerate(lines):
    try:
        json.loads(line)
    except json.JSONDecodeError:
        corrupt += 1
        print(f"      ❌ 行{i+1} JSON损坏")
print(f"   损坏: {corrupt}/{len(lines)}")
print(f"   有效: {len(lines) - corrupt}/{len(lines)}")

# 按source统计
from collections import Counter
sources = Counter()
for line in lines:
    sig = json.loads(line)
    sources[sig.get('source', '?')] += 1
print(f"   按发送者:")
for src, cnt in sources.most_common():
    print(f"      {src}: {cnt} 条")
print()

# ── 每个Agent的认知统计 ──
print("━━━ 认知统计 ━━━")
for agent in agents:
    print(f"   {agent.agent_id}:")
    for k, v in agent.brain._stats.items():
        print(f"      {k}: {v}")
print()

# ── 决策产出 ──
print("━━━ 决策 ━━━")
total_signals = graph.store.count()
print(f"   并发安全: {'✅ 通过' if corrupt == 0 else '❌ 失败'}")
print(f"   Brain独立: {'✅ 通过' if any(a.brain._stats['signals_ingested'] > 0 for a in agents) else '⚠️ 部分'}")
print(f"   JSONL完整性: {'✅ 通过' if corrupt == 0 else '❌ 失败'}")
print(f"\n━━━ 并发验证完成: {total_signals}信号, {N_AGENTS}Agent, 0损坏 ━━━")
