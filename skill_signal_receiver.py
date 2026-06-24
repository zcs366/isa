#!/usr/bin/env python3
"""
ISA skill_created信号接收器
============================
ISN创建skill → IO-S信号总线 → ISA接收 → Δ胶囊E层 + brain_dream.jsonl + RECALL

信号流: ISN → IO-S(signal_send) → ISA(signal_recv) → 三路写入

架构:
  poll_skill_created()  — 轮询IO-S获取skill_created信号
  process_skill_received() — 处理单条信号(写Δ胶囊E层+brain_dream+RECALL)
  start_receiver()      — 后台循环轮询(可独立进程或ISA Agent线程)
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("isa.skill_receiver")

# ── 路径 ──
JIAK_CARDS = Path.home() / ".hermes" / "jiak" / "cards"
JIAK_RECALL = Path.home() / ".hermes" / "jiak" / "RECALL.jsonl"
BRAIN_DIR = Path.home() / ".hermes" / "isa" / "brain"
DELTA_E_LAYER = Path.home() / ".hermes" / "isa" / "delta_e_layer.jsonl"

# ── IO-S syscall 接口 ──
_IO_S_URL = "http://127.0.0.1:8770/syscall"

def _sys_signal_recv(target: str = "isa", filter_type: str = "skill_created",
                     limit: int = 20) -> list:
    """通过HTTP POST接收IO-S信号。只接收指定filter_type。"""
    import urllib.request
    try:
        envelope = {
            "syscall": "signal_recv",
            "args": {"target": target, "filter": {"type": filter_type}, "limit": limit},
            "caller_pid": "isa",
        }
        data = json.dumps(envelope, ensure_ascii=False).encode()
        req = urllib.request.Request(_IO_S_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                return result.get("data", [])
        return []
    except Exception as e:
        logger.warning(f"signal_recv failed: {e}")
        return []


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


# ── Δ胶囊E层写入 ──
def append_to_e_layer(event: dict) -> bool:
    """写入Δ胶囊E层(原始事件日志)。"""
    try:
        DELTA_E_LAYER.parent.mkdir(parents=True, exist_ok=True)
        with open(DELTA_E_LAYER, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        logger.error(f"E layer write failed: {e}")
        return False


# ── brain_dream.jsonl 写入 ──
def append_to_brain_dream(agent_id: str, entry: dict) -> bool:
    """写入brain_dream.jsonl供DreamBridge消费。"""
    dream_log = BRAIN_DIR / agent_id / "brain_dream.jsonl"
    try:
        dream_log.parent.mkdir(parents=True, exist_ok=True)
        with open(dream_log, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        logger.error(f"brain_dream write failed: {e}")
        return False


# ── Payload安全验证 ──
def _validate_payload(payload: dict) -> dict:
    """验证skill_created payload安全性。"""
    name = payload.get("name", "")
    if not name:
        return {"ok": False, "error": "missing name"}
    if len(name) > 64:
        return {"ok": False, "error": f"name too long ({len(name)})"}
    if not all(c.isalnum() or c in '-_' for c in name):
        return {"ok": False, "error": f"name contains illegal chars: '{name}'"}
    desc = payload.get("description", "")
    if len(desc) > 1024:
        return {"ok": False, "error": f"description too long ({len(desc)})"}
    return {"ok": True}


# ── 核心处理 ──
def process_skill_received(signal: dict, agent_id: str = "军师") -> dict:
    """处理单条skill_created信号。

    Args:
        signal: IO-S信号 {type, from, payload: {name, description, category, keywords}}
        agent_id: 接收方Agent ID

    Returns:
        {ok, skill_name, writes: {e_layer, brain_dream, recall}}
    """
    payload = signal.get("payload", signal.get("data", {}))
    skill_name = payload.get("name", "unknown")
    ts = datetime.now(timezone.utc).isoformat()

    # P0安全验证
    validation = _validate_payload(payload)
    if not validation["ok"]:
        logger.warning(f"[ISA] skill_created rejected: {validation['error']}")
        return {"ok": False, "skill_name": skill_name, "error": validation["error"],
                "writes": {"e_layer": False, "brain_dream": False, "recall": False}}

    result = {
        "ok": True,
        "skill_name": skill_name,
        "writes": {"e_layer": False, "brain_dream": False, "recall": False},
    }

    # 1. Δ胶囊E层(原始事件)
    e_event = {
        "type": "skill_created",
        "source": "isn",
        "timestamp": ts,
        "data": payload,
        "_written_by": "isa",
    }
    result["writes"]["e_layer"] = append_to_e_layer(e_event)

    # 2. brain_dream.jsonl(DreamBridge消费)
    dream_entry = {
        "type": "skill_created",
        "event_type": "skill_created",
        "skill_name": skill_name,
        "skill_desc": payload.get("description", ""),
        "skill_cat": payload.get("category", ""),
        "keywords": payload.get("keywords", []),
        "agent_id": agent_id,
        "timestamp": ts,
    }
    result["writes"]["brain_dream"] = append_to_brain_dream(agent_id, dream_entry)

    # 3. RECALL(不可变追加+签名)
    import hashlib
    recall_entry = {
        "type": "skill_created_received",
        "from": "isn",
        "skill": skill_name,
        "category": payload.get("category", ""),
        "keywords": payload.get("keywords", []),
        "timestamp": ts,
        "_written_by": "isa",
        "_checksum": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16],
    }
    result["writes"]["recall"] = _sys_recall_append(recall_entry)

    logger.info(f"[ISA] Received skill_created: {skill_name} | "
                f"E:{result['writes']['e_layer']} D:{result['writes']['brain_dream']} "
                f"R:{result['writes']['recall']}")
    return result


# ── 轮询入口 ──
def poll_skill_created(agent_id: str = "军师") -> list:
    """轮询IO-S获取skill_created信号, 处理并返回结果列表。"""
    signals = _sys_signal_recv(target="isa", filter_type="skill_created")
    results = []
    for sig in signals:
        sig_type = sig.get("type", sig.get("meta", {}).get("type", ""))
        if sig_type == "skill_created":
            r = process_skill_received(sig, agent_id)
            results.append(r)
    return results


# ── 后台循环 ──
def start_receiver(agent_id: str = "军师", interval: int = 30,
                   on_receive: Callable = None) -> None:
    """后台循环轮询skill_created信号。

    Args:
        agent_id: 接收方Agent ID
        interval: 轮询间隔(秒)
        on_receive: 收到信号后的回调 (result_dict) -> None
    """
    logger.info(f"[ISA] skill_created receiver started (interval={interval}s)")
    while True:
        try:
            results = poll_skill_created(agent_id)
            for r in results:
                if on_receive:
                    on_receive(r)
        except Exception as e:
            logger.error(f"Receiver loop error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("[ISA] Testing skill_created receiver...")
    results = poll_skill_created()
    print(f"[ISA] Polled: {len(results)} skill_created signals processed")
    for r in results:
        print(f"  - {r['skill_name']}: {r['writes']}")
