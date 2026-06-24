#!/usr/bin/env python3
"""
ISA dream_insight信号发送器
============================
Dreaming发现关联 → 格式化 → IO-S信号总线 → ISN接收

信号流: ISA Brain.dream() → format_dream_insight() → IO-S(signal_send) → ISN

四种suggested_action:
  "create"  — ISN应创建新skill
  "update"  — ISN应更新现有skill
  "merge"   — ISN应合并多个skill
  "retire"  — ISN应退役某个skill
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("isa.dream_sender")

# ── IO-S syscall 接口 ──
_IO_S_URL = "http://127.0.0.1:8770/syscall"

def _sys_signal_send(signal_envelope: dict) -> Optional[str]:
    """通过HTTP POST发送IO-S信号（新信封格式）。"""
    import urllib.request
    try:
        envelope = {
            "syscall": "signal_send",
            "args": {"signal": signal_envelope},
            "caller_pid": "isa",
        }
        data = json.dumps(envelope, ensure_ascii=False).encode()
        req = urllib.request.Request(_IO_S_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                return result.get("data", {}).get("signal_id")
        return None
    except Exception as e:
        logger.warning(f"signal_send failed: {e}")
        return None


def _sys_recall_append(entry: dict) -> bool:
    """通过syscall层追加RECALL。"""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from syscall import recall_append
        return recall_append(entry, caller_pid="isa")
    except Exception as e:
        logger.warning(f"recall_append failed: {e}")
        return False


# ── 核心: 格式化+发送 ──
def format_dream_insight(discovery: dict, agent_id: str = "军师") -> dict:
    """将Brain.dream()的单条发现格式化为dream_insight信号。

    Args:
        discovery: Brain.dream()返回的单条 {card_a, card_b, shared_keywords, source}
        agent_id: 发送方Agent ID

    Returns:
        标准信封 {type, from, to, payload: {insight, related_skills, suggested_action, ...}}
    """
    card_a = discovery.get("card_a", "")
    card_b = discovery.get("card_b", "")
    shared = discovery.get("shared_keywords", [])
    source = discovery.get("source", "keyword")

    # 推断suggested_action
    # 如果两张卡都有内容→可能是merge; 如果只有一张→可能是create
    suggested_action = "update"  # 默认: 更新关联

    # 构建insight描述
    shared_str = ", ".join(shared[:5])
    insight = (f"卡片「{card_a}」与「{card_b}」发现关联 "
               f"(共享: {shared_str}, 来源: {source})")

    # 尝试从卡片提取related_skills
    related_skills = []
    for cid in [card_a, card_b]:
        try:
            card_path = Path.home() / ".hermes" / "jiak" / "cards" / f"{cid}.json"
            if card_path.exists():
                card = json.loads(card_path.read_text())
                # 卡片的related.skills字段
                skills = card.get("related", {}).get("skills", [])
                related_skills.extend(skills)
        except Exception:
            pass

    return {
        "type": "dream_insight",
        "from": agent_id,
        "to": "isn",
        "payload": {
            "insight": insight,
            "related_skills": list(set(related_skills)),
            "suggested_action": suggested_action,
            "card_a": card_a,
            "card_b": card_b,
            "shared_keywords": shared,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


def send_dream_insight(discovery: dict, agent_id: str = "军师") -> dict:
    """格式化并发送单条dream_insight到IO-S。

    Args:
        discovery: Brain.dream()返回的单条发现
        agent_id: 发送方Agent ID

    Returns:
        {ok, signal_id, insight}
    """
    envelope = format_dream_insight(discovery, agent_id)
    payload = envelope["payload"]

    # 发送到IO-S（新信封格式）
    signal_id = _sys_signal_send(envelope)

    # 记录到RECALL
    recall_entry = {
        "type": "dream_insight_sent",
        "from": agent_id,
        "to": "isn",
        "insight": payload["insight"][:200],
        "related_skills": payload["related_skills"],
        "suggested_action": payload["suggested_action"],
        "signal_id": signal_id,
        "timestamp": payload["timestamp"],
        "_written_by": "isa",
    }
    _sys_recall_append(recall_entry)

    ok = signal_id is not None
    logger.info(f"[ISA] dream_insight → ISN: {payload['insight'][:60]}... "
                f"action={payload['suggested_action']} ok={ok}")
    return {"ok": ok, "signal_id": signal_id, "insight": payload["insight"]}


def send_dream_insights_batch(discoveries: list, agent_id: str = "军师") -> list:
    """批量发送多条dream_insight。

    Args:
        discoveries: Brain.dream()返回的发现列表
        agent_id: 发送方Agent ID

    Returns:
        [{ok, signal_id, insight}, ...]
    """
    results = []
    for d in discoveries:
        r = send_dream_insight(d, agent_id)
        results.append(r)
    return results


# ── Dreaming→发送 一体化入口 ──
def dream_and_send(brain, agent_id: str = "军师") -> dict:
    """执行Dreaming并自动发送发现到ISN。

    Args:
        brain: Brain实例
        agent_id: Agent ID

    Returns:
        {discoveries: int, sent: int, results: [...]}
    """
    discoveries = brain.dream()
    if not discoveries:
        return {"discoveries": 0, "sent": 0, "results": []}

    results = send_dream_insights_batch(discoveries, agent_id)
    sent = sum(1 for r in results if r["ok"])

    logger.info(f"[ISA] dream_and_send: {len(discoveries)} discoveries, {sent} sent to ISN")
    return {
        "discoveries": len(discoveries),
        "sent": sent,
        "results": results,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("[ISA] Testing dream_insight sender...")
    # 模拟一条发现
    test_discovery = {
        "card_a": "isa-wave-mechanics",
        "card_b": "brain-dreaming",
        "shared_keywords": ["ISA", "语义"],
        "source": "keyword",
    }
    r = send_dream_insight(test_discovery)
    print(f"[ISA] Result: {r}")
