#!/usr/bin/env python3
"""
ISA ↔ IO-S syscall抽象层
=========================
所有共享资源的访问通过此层——不直接摸文件系统。

架构:
  ISA代码 → syscall.card_read() → [IO-S就绪? YES → cap_check → 返回]
                                   [NO → LOCAL_FALLBACK → 返回]

当IO-S的cap_policy.json建成后，LOCAL_FALLBACK替换为真实IO-S dispatch，
ISA业务代码不需要改——只改此文件的内部实现。

syscall列表:
  card_read(card_id, caller_pid)      — 读卡片
  card_write(card_id, data, caller_pid) — 写卡片
  signal_send(dest, body, caller_pid)   — 发信号
  signal_recv(filter, caller_pid)       — 读信号
  recall_append(entry, caller_pid)      — 追加RECALL
  recall_query(filter, caller_pid)      — 查RECALL
  agent_spawn(agent_id, caller_pid)     — 注册Agent（进程管理）
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("isa.syscall")

# ── IO-S就绪检测 ──
IO_S_KERNEL = Path.home() / ".io-s" / "kernel.json"
_HAS_IO_S = False  # 启动时检测

def _check_io_s():
    """检测IO-S是否在运行。就绪后切换为真实dispatch。"""
    global _HAS_IO_S
    if IO_S_KERNEL.exists():
        try:
            meta = json.loads(IO_S_KERNEL.read_text())
            _HAS_IO_S = meta.get("status") == "running"
        except Exception:
            _HAS_IO_S = False
    return _HAS_IO_S

# ── 路径 ──
JIAK_CARDS = Path.home() / ".hermes" / "jiak" / "cards"
JIAK_RECALL = Path.home() / ".hermes" / "jiak" / "RECALL.jsonl"
ISA_CHANNELS = Path.home() / ".hermes" / "isa" / "channels"

# ═══════════════════════════════════════
# syscall: card_read
# ═══════════════════════════════════════
def card_read(card_id: str, caller_pid: str = "isa") -> dict:
    """读取jika卡片。返回卡片数据dict，不存在返回{}。"""
    if _check_io_s():
        # TODO: IO-S dispatch
        # return io_s_dispatch("card_read", {"card_id": card_id, "caller_pid": caller_pid})
        pass
    
    # LOCAL FALLBACK
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
    """写入jika卡片。返回是否成功。"""
    if _check_io_s():
        # TODO: IO-S dispatch
        # return io_s_dispatch("card_write", {...})
        pass
    
    # LOCAL FALLBACK
    path = JIAK_CARDS / f"{card_id}.json"
    try:
        JIAK_CARDS.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        logger.warning(f"syscall.card_write({card_id}): {e}")
        return False

# ═══════════════════════════════════════
# syscall: recall_append
# ═══════════════════════════════════════
def recall_append(entry: dict, caller_pid: str = "isa") -> bool:
    """追加一行到RECALL.jsonl。"""
    if _check_io_s():
        pass
    try:
        JIAK_RECALL.parent.mkdir(parents=True, exist_ok=True)
        with open(JIAK_RECALL, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        logger.warning(f"syscall.recall_append: {e}")
        return False

# ═══════════════════════════════════════
# syscall: signal_send
# ═══════════════════════════════════════
def signal_send(dest: str, body: str, meta: dict = None,
                caller_pid: str = "isa") -> Optional[str]:
    """发送信号到语义场。返回signal_id或None。"""
    if _check_io_s():
        pass
    
    # LOCAL FALLBACK：直接写ChannelStore
    try:
        from isa import Signal, SignalGraph
        graph = SignalGraph("main", device_id=caller_pid)
        sig = Signal(type="message", source=caller_pid, target=dest, body=body, meta=meta or {})
        return graph.ingest(sig)
    except Exception as e:
        logger.warning(f"syscall.signal_send: {e}")
        return None

# ═══════════════════════════════════════
# syscall: signal_recv
# ═══════════════════════════════════════
def signal_recv(target: str = None, limit: int = 20, caller_pid: str = "isa") -> list:
    """读取信号。在IO-S就绪后走cap_check+审计。"""
    if _check_io_s():
        pass
    try:
        from isa import SignalGraph
        graph = SignalGraph("main", device_id=caller_pid)
        return graph.retrieve(target=target, limit=limit)
    except Exception as e:
        logger.warning(f"syscall.signal_recv: {e}")
        return []

# ═══════════════════════════════════════
# syscall: agent_spawn
# ═══════════════════════════════════════
def agent_spawn(agent_id: str, caller_pid: str = "isa") -> bool:
    """注册Agent到进程表。IO-S就绪后继承cap。"""
    if _check_io_s():
        pass
    # LOCAL FALLBACK: 只创建Brain目录
    brain_dir = Path.home() / ".hermes" / "isa" / "brain" / agent_id
    brain_dir.mkdir(parents=True, exist_ok=True)
    return True

# ═══════════════════════════════════════
# 快捷集成：替换ISA核心模块的导入
# ═══════════════════════════════════════
def patch_isa_core():
    """替换isa.py/brain.py中的直接文件操作为syscall。"""
    # 此函数在IO-S就绪时调用，替换全局函数指针
    logger.info("ISA syscall层就绪：IO-S dispatch模式")
    _check_io_s()
