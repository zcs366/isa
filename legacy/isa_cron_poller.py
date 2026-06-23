#!/usr/bin/env python3
"""
ISA Cron 消息轮询器 — LEGACY
=============================

定位：ISA Chat Gateway WebSocket 上线前的老式轮询模式。
      每 tick 检查 SignalGraph 中的新信号 → 调用 isa_agent_processor.py 处理 → 回复。

被取代时间：2026-06-22 ISA Chat 方向纠正后。
取代者：Gateway WebSocket（推送模式而非轮询模式）。

保留价值：无 Gateway 环境的纯 CLI 离线场景备用方案，
         以及轮询模式的参考实现（状态文件 + 去重 + 超时处理）。

原文件名：isa_yuanbao_listener.py（2026-06-22 重命名至此）
"""

import json
import os
import sys
import time
from pathlib import Path

ISA_DIR = Path.home() / "projects" / "isa"
sys.path.insert(0, str(ISA_DIR))

from isa import SignalGraph, DEFAULT_CHANNEL


def main():
    graph = SignalGraph(DEFAULT_CHANNEL, device_id="yuanbao-listener")
    graph.index.rebuild()
    
    # 状态文件——记录上次处理到的信号 ID
    state_path = Path.home() / ".hermes" / "isa" / "yuanbao" / ".listener_state.json"
    
    last_id = None
    if state_path.exists():
        try:
            last_id = json.loads(state_path.read_text()).get("last_signal_id")
        except Exception:
            pass
    
    # 检索发给 isa-bot 的最新信号
    signals = graph.retrieve(target="isa-bot", limit=5)
    
    if not signals:
        # 没有新信号——回写心跳时间戳
        state_path.write_text(json.dumps({
            "last_seen": time.time(),
            "last_signal_id": last_id,
        }))
        return  # 静默退出——cronjob 正确模式
    
    processed = 0
    latest_id = last_id
    
    for sig in signals:
        if sig.source == "isa-bot" or sig.source == "gateway":
            continue
        if last_id and sig.id == last_id:
            break  # 已处理过
        if latest_id and sig.timestamp <= (latest_id if isinstance(latest_id, str) else "0"):
            continue
        
        # 发新信号 → 通过桥接器处理
        user_id = sig.source
        message = sig.body
        
        # 调用桥接器
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ISA_DIR / "isa_agent_processor.py"),
             "--user", user_id, "--msg", message, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        
        if result.returncode != 0:
            print(f"[isa-listener] ❌ 处理失败: {user_id}: {result.stderr[:200]}")
            continue
        
        try:
            data = json.loads(result.stdout.strip().split("\n")[-1])
        except (json.JSONDecodeError, IndexError):
            print(f"[isa-listener] ❌ 解析失败: {result.stdout[:200]}")
            continue
        
        response = data.get("response", "")
        
        # 回复写入 ISA
        from isa import Signal
        reply = Signal(
            type="message",
            source="isa-bot",
            target=user_id,
            body=response,
            meta={"via": "yuanbao-listener"},
        )
        graph.ingest(reply)
        graph.index.rebuild()
        
        print(f"[isa-listener] ✅ {user_id}: ...{response[:40]}")
        processed += 1
        latest_id = sig.id
    
    # 保存状态
    state_path.write_text(json.dumps({
        "last_seen": time.time(),
        "last_signal_id": latest_id or last_id,
        "processed": processed,
    }))


if __name__ == "__main__":
    main()
