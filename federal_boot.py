#!/usr/bin/env python3
"""
联邦启动器 v2.0 — session启动时自动完成：
  1. 检查注册（未注册→三层fallback自动注册）
  2. whoami（返回agent_id）
  3. scan（未读wink）
  4. online（声明在线 + 更新静默状态机）
  5. 工具箱注入

用法:
  python3 federal_boot.py <session_id>
  python3 federal_boot.py <session_id> --quiet   # 静默模式（只返回agent_id）
"""

import json, os, sys, re
from datetime import datetime, timezone

RECALL = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")
REGISTRY = os.path.expanduser("~/.hermes/jiak/federal_registry.json")
ISA_HOME = os.path.expanduser("~/projects/isa")

# ─── RECALL读写 ─────────────────────────────────────

def load_events():
    events = []
    if not os.path.exists(RECALL):
        return events
    with open(RECALL) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: events.append(json.loads(line))
            except: pass
    return events

def append_event(event):
    with open(RECALL, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

# ─── 注册表 ─────────────────────────────────────────

def get_my_agent_id(session_id):
    """从RECALL查找自己的agent_id"""
    events = load_events()
    for e in events:
        if e.get("type") in ("federal_register", "agent_registered") and e.get("session_id") == session_id:
            return e.get("agent_id")
    return None

def is_registered(session_id):
    """检查session是否已注册"""
    return get_my_agent_id(session_id) is not None

def get_registered_agents():
    """获取所有已注册的agent_id"""
    events = load_events()
    agents = {}
    for e in events:
        if e.get("type") in ("federal_register", "agent_registered"):
            agents[e["agent_id"]] = e.get("session_id", "?")
    return agents

# ─── 三层fallback提取agent_id ──────────────────────

def extract_agent_id_from_prompt(prompt):
    """层1: 从系统提示词提取agent_id"""
    if not prompt:
        return None
    patterns = [
        r'你是(\w+)窗口',
        r'你是(\w+)\s*(?:Agent|智能体)',
        r'agent_id[:\s]*["\']?(\w+)["\']?',
        r'军师窗口.*?(\w+).*?就位',
        r'角色[：:]\s*(\w+)',
    ]
    for p in patterns:
        m = re.search(p, prompt)
        if m:
            return m.group(1).lower()
    return None

def extract_agent_id_from_message(msg):
    """层2: 从用户消息提取agent_id"""
    if not msg:
        return None
    patterns = [
        r'我是(\w+)窗口',
        r'我是(\w+)',
        r'agent_id[:\s]*["\']?(\w+)["\']?',
    ]
    for p in patterns:
        m = re.search(p, msg)
        if m:
            candidate = m.group(1).lower()
            if candidate not in ('我', '你', '他', '她', '它'):
                return candidate
    return None

def auto_register(session_id, system_prompt="", user_message="", sender_id=""):
    """三层fallback自动注册"""
    agent_id = extract_agent_id_from_prompt(system_prompt)
    if not agent_id:
        agent_id = extract_agent_id_from_message(user_message)
    if not agent_id:
        agent_id = sender_id if sender_id and sender_id != "?" else f"sa_{session_id[:8]}"
    # 临时ID标记：如果是自动生成的，前缀sa_表示待人工确认

    # 写注册事件
    append_event({
        "type": "agent_registered",
        "agent_id": agent_id,
        "session_id": session_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "registered_by": "federal_boot.py",
        "_written_by": "federal_boot.py"
    })
    return agent_id

# ─── Wink ───────────────────────────────────────────

def get_undelivered_winks(agent_id):
    """获取发给自己的未投递wink"""
    events = load_events()
    delivered_ts = {(e.get("wink_ts"), e.get("from_agent"), e.get("to_agent"))
                    for e in events if e.get("type") == "wink_delivered"}
    winks = []
    for w in events:
        if w.get("type") != "wink": continue
        if (w.get("ts"), w.get("from_agent"), w.get("to_agent")) in delivered_ts: continue
        if w.get("to_agent") not in (agent_id, "*"): continue
        winks.append(w)
    return winks

# ─── 在线Agent ──────────────────────────────────────

def get_online_agents():
    """获取当前在线的agent列表"""
    events = load_events()
    online = set()
    for e in events:
        if e.get("type") == "agent_online":
            online.add(e.get("agent_id"))
        elif e.get("type") == "agent_offline":
            online.discard(e.get("agent_id"))
    return online

# ─── 静默状态 ──────────────────────────────────────

def get_silence_states():
    """获取所有SA的静默状态"""
    try:
        sys.path.insert(0, ISA_HOME)
        from silence_state import build_state_machines, load_events as silence_load
        events = silence_load()
        machines = build_state_machines(events)
        states = {}
        for agent_id, m in machines.items():
            state, alert, reason = m.check()
            states[agent_id] = {
                "state": state.value,
                "name": state.name,
                "alert": alert,
                "reason": reason,
                "last_wink": m.last_wink.isoformat()[:19] if m.last_wink else None,
                "declaration": m.declaration
            }
        return states
    except Exception:
        return {}

# ─── 主函数 ─────────────────────────────────────────

def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HERMES_SESSION_ID", "")
    quiet = "--quiet" in sys.argv

    if not session_id:
        print("用法: federal_boot.py <session_id> [--quiet]")
        sys.exit(1)

    # 1. 检查注册（未注册→自动注册）
    agent_id = get_my_agent_id(session_id)
    if not agent_id:
        agent_id = auto_register(session_id)
        if not quiet:
            print(f"🆕 自动注册: {agent_id} (session={session_id[:8]})")

    # 2. 声明在线
    append_event({
        "type": "agent_online",
        "agent_id": agent_id,
        "session_id": session_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "_written_by": "federal_boot.py"
    })

    # 3. 获取状态
    winks = get_undelivered_winks(agent_id)
    registered = get_registered_agents()
    online = get_online_agents()
    silence = get_silence_states()

    if quiet:
        print(agent_id)
        return

    # 4. 输出启动信息（新格式）
    print(f"🔮 联邦启动 · agent_id = {agent_id}")
    print(f"│")
    print(f"├─ 📋 注册表：{len(registered)}/{len(registered)} Agent已注册")
    print(f"├─ 💬 未读wink：{len(winks)}条")

    # 在线Agent
    online_list = sorted(online & set(registered.keys()))
    if online_list:
        print(f"├─ 🟢 在线Agent：{', '.join(online_list)}")

    # 静默Agent
    silent = [aid for aid, s in silence.items()
              if s["state"] == "🔵" and aid in registered]
    if silent:
        for aid in silent:
            s = silence[aid]
            reason = s.get("declaration", {}).get("reason", "") if s.get("declaration") else ""
            print(f"├─ 🔵 静默中：{aid}（{reason}）")

    # 未读wink详情
    if winks:
        print(f"│")
        print(f"├─ 📬 未读消息:")
        for w in winks[:5]:
            ts = w.get("ts", "?")[:19]
            fr = w.get("from_agent", "?")
            to = w.get("to_agent", "?")
            st = w.get("signal_type", "?")
            summary = w.get("payload", {}).get("summary", "")[:50]
            print(f"│  [{ts}] {fr}→{to} ({st}) {summary}")
        if len(winks) > 5:
            print(f"│  ... 还有{len(winks)-5}条")

    # 工具箱
    print(f"│")
    print(f"└─ 🧰 工具箱")
    print(f"   ├─ python3 ~/projects/isa/federal_toolbox.py who")
    print(f"   ├─ python3 ~/projects/isa/federal_toolbox.py scan")
    print(f"   ├─ python3 ~/projects/isa/federal_toolbox.py status")
    print(f"   ├─ python3 ~/projects/isa/federal_toolbox.py wink --fr {agent_id} --to <target> --summary \"<msg>\"")
    print(f"   └─ python3 ~/projects/isa/silence_state.py scan")

if __name__ == "__main__":
    main()
