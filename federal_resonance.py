#!/usr/bin/env python3
"""
联邦共振系统 —— 让TUI/CLI Agent加入跨频道感知网络

三个信号：
- agent_online:  Agent上线声明（presence）
- wink:          Agent有话要说（信号投递）
- agent_offline: Agent下线声明

所有信号走RECALL（带_written_by签名）。
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

RECALL_SCRIPT = os.path.expanduser("~/.hermes/jiak/recall_append.py")


def _make_recall_record(record: dict) -> bool:
    """通过recall_append.py写入RECALL（带签名审计链）"""
    try:
        result = subprocess.run(
            ["python3", RECALL_SCRIPT, json.dumps(record, ensure_ascii=False)],
            capture_output=True, timeout=10, text=True
        )
        if result.returncode == 0:
            return True
        else:
            print(f"RECALL写入失败: {result.stderr}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"RECALL调用异常: {e}", file=sys.stderr)
        return False


def agent_online(agent_id: str, session_id: str = None, detail: str = ""):
    """
    Agent上线声明——写presence到RECALL

    参数:
        agent_id: Agent标识（如 "junshi", "octopus"）
        session_id: 可选，当前会话ID
        detail: 可选，上线说明
    """
    now = datetime.now(timezone.utc)
    record = {
        "type": "agent_online",
        "agent_id": agent_id,
        "session_id": session_id or f"{agent_id}_{now.strftime('%Y%m%d_%H%M%S')}",
        "online_at": now.isoformat(),
        "detail": detail
    }
    ok = _make_recall_record(record)
    if ok:
        print(f"[联邦共振] ✅ {agent_id} 上线")
    return ok


def agent_wink(from_agent: str, to_agent: str, signal_type: str,
               summary: str, deliverable_path: str = None,
               requires_response: bool = False):
    """
    Agent发送wink信号到RECALL

    signal_type: delivery(交付) / discovery(发现) / alert(告警) / handshake(握手)
    summary: 一句话说明
    deliverable_path: 交付物的路径
    """
    now = datetime.now(timezone.utc)
    record = {
        "type": "wink",
        "from_agent": from_agent,
        "to_agent": to_agent,
        "signal_type": signal_type,
        "ts": now.isoformat(),
        "payload": {
            "summary": summary,
            "deliverable_path": deliverable_path or ""
        },
        "delivered_at": None,
        "requires_response": requires_response
    }
    ok = _make_recall_record(record)
    if ok:
        to_str = to_agent if to_agent != "*" else "所有Agent"
        print(f"[联邦共振] ✅ {from_agent} → {to_str} [{signal_type}] {summary}")
    return ok


def agent_offline(agent_id: str, session_id: str = None):
    """
    Agent下线声明——写offline到RECALL
    """
    now = datetime.now(timezone.utc)
    record = {
        "type": "agent_offline",
        "agent_id": agent_id,
        "session_id": session_id or "",
        "offline_at": now.isoformat()
    }
    ok = _make_recall_record(record)
    if ok:
        print(f"[联邦共振] ✅ {agent_id} 下线")
    return ok


def list_undelivered_winks(target_agent: str = None, max_lines: int = 200):
    """
    扫描RECALL中未投递的wink。

    三重防重复:
    1. delivered_at != null (原始记录标记)
    2. wink_delivered 标记存在 (消费追加记录)
    3. 每次调用独立扫描——dedup_state在调用方（build_injection）维护

    供jika注入hook调用（每轮对话都扫，三重防线保证不重复注入）。
    """
    recall_path = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")
    if not os.path.exists(recall_path):
        return []

    with open(recall_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 第一遍：收集wink_delivered标记（已投递wink的ts集合）
    delivered_tss = set()
    for line in reversed(lines[-max_lines:]):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") == "wink_delivered":
            wink_ts = record.get("wink_ts")
            if wink_ts:
                delivered_tss.add(wink_ts)

    # 第二遍：收集未投递wink
    undelivered = []
    for line in lines[-max_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "wink":
            continue
        # 防线①: delivered_at直接标记
        if record.get("delivered_at") is not None:
            continue
        # 防线②: wink_delivered追加标记
        if record.get("ts") in delivered_tss:
            continue
        # 防线③: target_agent匹配
        if target_agent and target_agent != "*":
            to_agents = record.get("to_agent", "")
            if isinstance(to_agents, str):
                to_agents = [to_agents]
            if target_agent not in to_agents and "*" not in to_agents:
                continue
        undelivered.append(record)

    return undelivered


def get_latest_presence(agent_id: str = None) -> dict:
    """读取RECALL中最近的上线记录（presence）。

    返回最近一条agent_online记录。agent_id指定则只返回该Agent的。
    用于注入hook获取当前session的身份——"我是谁"。
    """
    recall_path = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")
    if not os.path.exists(recall_path):
        return {}

    with open(recall_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 从后往前扫描，找agent_online记录
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "agent_online":
            continue
        if agent_id and record.get("agent_id") != agent_id:
            continue
        return record

    return {}


def mark_delivered(wink_record: dict):
    """
    标记wink为已投递——更新delivered_at。
    直接追加一条'wink_delivered'标记到RECALL。
    """
    now = datetime.now(timezone.utc)
    marker = {
        "type": "wink_delivered",
        "wink_ts": wink_record.get("ts"),
        "from_agent": wink_record.get("from_agent"),
        "delivered_at": now.isoformat()
    }
    return _make_recall_record(marker)


# ============================================================
# CLI入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  federal_resonance.py online --agent <id> [--session <sid>] [--detail <text>]")
        print("  federal_resonance.py wink --from <id> --to <id> --type <delivery|discovery|alert|handshake> --summary <text> [--deliverable <path>] [--response]")
        print("  federal_resonance.py offline --agent <id> [--session <sid>]")
        print("  federal_resonance.py scan [--to <agent_id>]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "online":
        args = _parse_args(sys.argv[2:])
        agent_online(
            agent_id=args.get("--agent", ""),
            session_id=args.get("--session"),
            detail=args.get("--detail", "")
        )

    elif cmd == "wink":
        args = _parse_args(sys.argv[2:])
        agent_wink(
            from_agent=args.get("--from", ""),
            to_agent=args.get("--to", ""),
            signal_type=args.get("--type", "delivery"),
            summary=args.get("--summary", ""),
            deliverable_path=args.get("--deliverable"),
            requires_response="--response" in sys.argv
        )

    elif cmd == "offline":
        args = _parse_args(sys.argv[2:])
        agent_offline(
            agent_id=args.get("--agent", ""),
            session_id=args.get("--session")
        )

    elif cmd == "scan":
        args = _parse_args(sys.argv[2:])
        winks = list_undelivered_winks(target_agent=args.get("--to"))
        if winks:
            print(f"[联邦共振] 未投递wink: {len(winks)}条")
            for w in winks:
                print(f"  {w['from_agent']} → {w['to_agent']} [{w['signal_type']}] {w['payload']['summary']}")
        else:
            print("[联邦共振] 无未投递wink")

    else:
        print(f"未知命令: {cmd}", file=sys.stderr)
        sys.exit(1)


def _parse_args(argv):
    """简单key-value参数解析"""
    args = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                args[key] = argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1
    return args


if __name__ == "__main__":
    main()
