#!/usr/bin/env python3
"""
ISA ↔ IO-S syscall抽象层 v1.1
==============================
所有共享资源的访问通过此层——不直接摸文件系统。

架构:
  ISA代码 → syscall.card_read() → [IO-S就绪? YES → IO-S dispatch (cap_check + 审计)]
                                   [NO → LOCAL_FALLBACK (直接读写文件)]

切换条件: ~/.io-s/kernel.json {status:"running", cap_policy_loaded:true}

IO-S v1.0 确认:
  - 16个注册syscall
  - 4类cap资源: card, process, signal, cap_policy
  - 零root: cap_policy不可改
  - caller_pid格式: "p-{id}"
  - 请求格式: {syscall, args{resource,operation,...}, caller_pid, trace_id}

syscall列表 (对齐IO-S 16个):
  card_read(card_id)        — 读卡片
  card_write(card_id, data) — 写卡片
  card_list(filter)         — 列卡片
  signal_send(dest, body)   — 发信号
  signal_recv(limit)        — 收信号
  signal_broadcast(body)    — 广播到频道
  recall_append(entry)      — 追加RECALL
  recall_query(filter)      — 查RECALL
  agent_spawn(agent_id)     — 注册Agent
  agent_kill(agent_id)      — 终止Agent
  agent_status(agent_id)   — 查Agent状态
  agent_list()              — 列Agent
  dream_launch()            — 启动梦境 (纯认知, 无资源访问)
  dream_report()            — 读梦境结果 (纯认知, 无资源访问)
  sys_stats()               — IO-S自身状态 (IO-S独有, ISA只读)
  io_s_ping()               — 健康检查
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("isa.syscall")

# ── IO-S kernel 信号 ──
_IO_S_KERNEL = Path.home() / ".io-s" / "kernel.json"
_HAS_IO_S = False

def _check_io_s() -> bool:
    """检测IO-S是否在线。每次dispatch前检查。"""
    global _HAS_IO_S
    if _HAS_IO_S:
        return True  # 已确认过，不再重复检查
    if _IO_S_KERNEL.exists():
        try:
            state = json.loads(_IO_S_KERNEL.read_text())
            if state.get("status") == "running" and state.get("cap_policy_loaded"):
                _HAS_IO_S = True
                logger.info("🟢 syscall: IO-S在线, 切换真实dispatch")
                return True
        except Exception:
            pass
    return False

# ── 路径 (LOCAL_FALLBACK用) ──
JIAK_CARDS = Path.home() / ".hermes" / "jiak" / "cards"
JIAK_RECALL = Path.home() / ".hermes" / "jiak" / "RECALL.jsonl"

# ── 信封构建 ──
def _make_envelope(syscall: str, resource: str, operation: str,
                   extra: dict = None, caller_pid: str = "isa") -> dict:
    """构建IO-S标准请求信封。"""
    return {
        "syscall": syscall,
        "args": {
            "resource": resource,
            "operation": operation,
            **(extra or {}),
        },
        "caller_pid": caller_pid,
        "trace_id": f"trc-{uuid.uuid4().hex[:12]}",
    }

def _io_s_dispatch(envelope: dict) -> dict:
    """向IO-S发送syscall并返回响应。
    
    TODO: IO-S dispatch通道待定义 (socket/HTTP/stdin?)
    当前: 返回LOCAL_FALLBACK结果
    """
    # TODO: 替换为真实IO-S dispatch
    # 例如: HTTP POST to IO-S syscall endpoint
    # or: unix socket
    # or: stdin/stdout subprocess
    logger.warning(f"syscall: IO-S dispatch未实现, 使用LOCAL_FALLBACK")
    return {"ok": False, "error": {"code": "NOT_IMPLEMENTED", "message": "IO-S dispatch通道待实现"}, "trace_id": envelope.get("trace_id", "")}

# ═══════════════════════════════════════
# syscall: card_read
# ═══════════════════════════════════════
def card_read(card_id: str, caller_pid: str = "isa") -> dict:
    """读取jika卡片。"""
    if _check_io_s():
        env = _make_envelope("card_read", "card", "read", {"card_id": card_id}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return resp.get("data", {})
        # fallthrough to LOCAL_FALLBACK on error
    
    path = JIAK_CARDS / f"{card_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"syscall.card_read({card_id}): {e}")
        return {}

# ═══════════════════════════════════════
# syscall: card_write
# ═══════════════════════════════════════
def card_write(card_id: str, data: dict, caller_pid: str = "isa") -> bool:
    """写入jika卡片。"""
    if _check_io_s():
        env = _make_envelope("card_write", "card", "write",
                            {"card_id": card_id, "data": data}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return True
    
    path = JIAK_CARDS / f"{card_id}.json"
    try:
        JIAK_CARDS.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        logger.warning(f"syscall.card_write({card_id}): {e}")
        return False

# ═══════════════════════════════════════
# syscall: card_list
# ═══════════════════════════════════════
def card_list(pattern: str = "*.json", caller_pid: str = "isa") -> list:
    """列卡片。"""
    if _check_io_s():
        env = _make_envelope("card_list", "card", "read", {"pattern": pattern}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return resp.get("data", [])
    try:
        return sorted([p.stem for p in JIAK_CARDS.glob(pattern)])
    except Exception:
        return []

# ═══════════════════════════════════════
# syscall: recall_append
# ═══════════════════════════════════════
def recall_append(entry: dict, caller_pid: str = "isa") -> bool:
    """追加RECALL。"""
    if _check_io_s():
        env = _make_envelope("recall_append", "signal", "write",
                            {"entry": entry}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return True
    try:
        JIAK_RECALL.parent.mkdir(parents=True, exist_ok=True)
        with open(JIAK_RECALL, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        logger.warning(f"syscall.recall_append: {e}")
        return False

# ═══════════════════════════════════════
# syscall: recall_query
# ═══════════════════════════════════════
def recall_query(filter_key: str = None, caller_pid: str = "isa") -> list:
    """查RECALL。"""
    if _check_io_s():
        env = _make_envelope("recall_query", "signal", "read",
                            {"filter": filter_key}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return resp.get("data", [])
    try:
        if not JIAK_RECALL.exists():
            return []
        lines = JIAK_RECALL.read_text().strip().split("\n")
        if not filter_key:
            return [json.loads(l) for l in lines if l.strip()]
        return [json.loads(l) for l in lines if l.strip() and filter_key in l]
    except Exception:
        return []

# ═══════════════════════════════════════
# syscall: signal_send / signal_recv / signal_broadcast
# ═══════════════════════════════════════
def signal_send(dest: str, body: str, meta: dict = None, caller_pid: str = "isa") -> Optional[str]:
    """发信号。"""
    if _check_io_s():
        env = _make_envelope("signal_send", "signal", "send",
                            {"dest": dest, "body": body, "meta": meta or {}}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return resp.get("data", {}).get("signal_id")
    try:
        from isa import Signal, SignalGraph
        graph = SignalGraph("main", device_id=caller_pid)
        sig = Signal(type="message", source=caller_pid, target=dest, body=body, meta=meta or {})
        return graph.ingest(sig)
    except Exception as e:
        logger.warning(f"syscall.signal_send: {e}")
        return None

def signal_recv(target: str = None, limit: int = 20, caller_pid: str = "isa") -> list:
    """收信号。"""
    if _check_io_s():
        env = _make_envelope("signal_recv", "signal", "recv",
                            {"target": target, "limit": limit}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return resp.get("data", [])
    try:
        from isa import SignalGraph
        graph = SignalGraph("main", device_id=caller_pid)
        return graph.retrieve(target=target, limit=limit)
    except Exception:
        return []

def signal_broadcast(body: str, importance: float = 0.5, caller_pid: str = "isa") -> Optional[str]:
    """广播到频道。"""
    return signal_send("*", body, {"importance": importance}, caller_pid)

# ═══════════════════════════════════════
# syscall: agent_spawn / agent_kill / agent_status / agent_list
# ═══════════════════════════════════════
def agent_spawn(agent_id: str, caller_pid: str = "isa") -> bool:
    """注册Agent。"""
    if _check_io_s():
        env = _make_envelope("agent_spawn", "process", "spawn", {"agent_id": agent_id}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return True
    brain_dir = Path.home() / ".hermes" / "isa" / "brain" / agent_id
    brain_dir.mkdir(parents=True, exist_ok=True)
    return True

def agent_kill(agent_id: str, caller_pid: str = "isa") -> bool:
    """终止Agent。"""
    if _check_io_s():
        env = _make_envelope("agent_kill", "process", "kill", {"agent_id": agent_id}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return True
    return False  # LOCAL_FALLBACK不支持kill

def agent_status(agent_id: str, caller_pid: str = "isa") -> dict:
    """查Agent状态。"""
    if _check_io_s():
        env = _make_envelope("agent_status", "process", "read", {"agent_id": agent_id}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return resp.get("data", {})
    return {"agent_id": agent_id, "status": "unknown"}

def agent_list(caller_pid: str = "isa") -> list:
    """列Agent。"""
    if _check_io_s():
        env = _make_envelope("agent_list", "process", "read", {}, caller_pid)
        resp = _io_s_dispatch(env)
        if resp.get("ok"):
            return resp.get("data", [])
    brain_root = Path.home() / ".hermes" / "isa" / "brain"
    if brain_root.exists():
        return [d.name for d in brain_root.iterdir() if d.is_dir()]
    return []

# ═══════════════════════════════════════
# syscall: dream_launch / dream_report (纯认知, 无cap_check)
# ═══════════════════════════════════════
def dream_launch(caller_pid: str = "isa") -> bool:
    """启动梦境。纯认知操作，无需cap_check。"""
    try:
        from isa import IsaAgent, SignalGraph
        agent = IsaAgent(caller_pid, graph=SignalGraph("main", device_id=caller_pid))
        return len(agent.brain.dream()) > 0
    except Exception:
        return False

def dream_report(caller_pid: str = "isa") -> list:
    """读梦境结果。"""
    try:
        from isa import IsaAgent, SignalGraph
        agent = IsaAgent(caller_pid, graph=SignalGraph("main", device_id=caller_pid))
        return agent.brain.dream()
    except Exception:
        return []

# ═══════════════════════════════════════
# syscall: sys_stats (IO-S独有, ISA只读)
# ═══════════════════════════════════════
def sys_stats(caller_pid: str = "isa") -> dict:
    """IO-S自身状态。"""
    if _check_io_s():
        try:
            return json.loads(_IO_S_KERNEL.read_text())
        except Exception:
            pass
    return {"status": "local_fallback", "message": "IO-S不在线, 使用本地模式"}
