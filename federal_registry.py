#!/usr/bin/env python3
"""
联邦注册表 —— session_id → agent_id 映射

三API：
- register(session_id, agent_id) — Agent上线注册
- unregister(session_id) — Agent下线注销
- lookup(agent_id) → [session_ids] — 查agent_id的活跃session

注册表存储：~/.hermes/jiak/federal_registry.json
所有注册/注销操作走 RECALL 审计轨迹。
零LLM，纯JSON操作。
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

REGISTRY_PATH = os.path.expanduser("~/.hermes/jiak/federal_registry.json")
RECALL_SCRIPT = os.path.expanduser("~/.hermes/jiak/recall_append.py")


def _read_registry() -> dict:
    """读取注册表"""
    if not os.path.exists(REGISTRY_PATH):
        return {"mappings": [], "generated": ""}
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"mappings": [], "generated": ""}


def _write_registry(registry: dict) -> None:
    """写入注册表"""
    registry["generated"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def _recall_append(record: dict) -> bool:
    """走recall_append.py写入审计轨迹（带Hash去重）"""
    try:
        result = subprocess.run(
            ["python3", RECALL_SCRIPT, "--json", json.dumps(record, ensure_ascii=False)],
            capture_output=True, timeout=10, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            resp = json.loads(result.stdout.strip())
            return resp.get("ok", False)
        return result.returncode == 0
    except Exception:
        return False


def register(session_id: str, agent_id: str) -> bool:
    """
    Agent上线注册——session_id → agent_id 映射。
    如果session_id已注册则更新agent_id。
    """
    registry = _read_registry()
    mappings = registry.get("mappings", [])

    # 去重：同session_id已有映射则更新
    found = False
    for m in mappings:
        if m["session_id"] == session_id:
            m["agent_id"] = agent_id
            m["registered_at"] = datetime.now(timezone.utc).isoformat()
            found = True
            break

    if not found:
        mappings.append({
            "session_id": session_id,
            "agent_id": agent_id,
            "registered_at": datetime.now(timezone.utc).isoformat()
        })

    registry["mappings"] = mappings
    _write_registry(registry)

    # RECALL审计轨迹
    _recall_append({
        "type": "federal_register",
        "session_id": session_id,
        "agent_id": agent_id
    })

    return True


def unregister(session_id: str) -> bool:
    """
    Agent下线注销——移除session_id映射。
    保留agent_id（agent_id不因session断开而消失，允许重连）。
    """
    registry = _read_registry()
    mappings = registry.get("mappings", [])

    removed = [m for m in mappings if m["session_id"] == session_id]
    mappings = [m for m in mappings if m["session_id"] != session_id]

    registry["mappings"] = mappings
    _write_registry(registry)

    if removed:
        _recall_append({
            "type": "federal_unregister",
            "session_id": session_id,
            "agent_id": removed[0].get("agent_id", "unknown")
        })
        return True
    return False


def lookup(agent_id: str) -> list:
    """
    查agent_id的活跃session列表。
    一个Agent可在多个session中并行存在（TUI+飞书同时开）。
    """
    registry = _read_registry()
    return [
        m for m in registry.get("mappings", [])
        if m["agent_id"] == agent_id
    ]


def lookup_session(session_id: str) -> Optional[dict]:
    """通过session_id查映射（反向查找）"""
    registry = _read_registry()
    for m in registry.get("mappings", []):
        if m["session_id"] == session_id:
            return m
    return None


def list_active_agents() -> list:
    """列出所有活跃Agent（去重）"""
    registry = _read_registry()
    agents = set()
    for m in registry.get("mappings", []):
        agents.add(m["agent_id"])
    return sorted(agents)


def list_active_sessions(agent_id: str = None) -> list:
    """列出所有活跃session。指定agent_id则只列该Agent的。"""
    registry = _read_registry()
    if agent_id:
        return [m["session_id"] for m in registry.get("mappings", [])
                if m["agent_id"] == agent_id]
    return [m["session_id"] for m in registry.get("mappings", [])]


# ============================================================
# CLI入口
# ============================================================

def main():
    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  register --session <sid> --agent <id>")
        print("  unregister --session <sid>")
        print("  lookup --agent <id>")
        print("  list [--agent <id>]")
        sys.exit(1)

    cmd = sys.argv[1]
    args = {}
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:]
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                args[key] = sys.argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1

    if cmd == "register":
        register(args.get("session", ""), args.get("agent", ""))
        print(f"[联邦注册表] ✅ {args.get('agent')} 在线 (session={args.get('session')})")
    elif cmd == "unregister":
        unregister(args.get("session", ""))
        print(f"[联邦注册表] ✅ session={args.get('session')} 已注销")
    elif cmd == "lookup":
        results = lookup(args.get("agent", ""))
        if results:
            print(f"[联邦注册表] {args.get('agent')} 活跃session: {len(results)}个")
            for r in results:
                print(f"  session={r['session_id']}  since={r['registered_at']}")
        else:
            print(f"[联邦注册表] {args.get('agent')} 无活跃session")
    elif cmd == "list":
        agent = args.get("agent")
        if agent:
            sessions = list_active_sessions(agent)
            print(f"[联邦注册表] {agent} 的session: {sessions}")
        else:
            agents = list_active_agents()
            print(f"[联邦注册表] 活跃Agent ({len(agents)}): {agents}")


if __name__ == "__main__":
    main()
