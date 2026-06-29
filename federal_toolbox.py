#!/usr/bin/env python3
"""联邦工具箱 — scan/who/online/offline/status"""

import json, sys, os, argparse
from collections import Counter
from datetime import datetime

RECALL = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")

def load_events():
    events = []
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

def cmd_status(args):
    """联邦全景"""
    events = load_events()
    registered = {e["agent_id"]: e.get("session_id","?") for e in events if e.get("type") == "agent_registered"}
    online = set()
    for e in events:
        if e.get("type") == "agent_online": online.add(e.get("agent_id"))
        elif e.get("type") == "agent_offline": online.discard(e.get("agent_id"))
    winks = [e for e in events if e.get("type") == "wink"]
    delivered_ts = {(e.get("wink_ts"), e.get("from_agent"), e.get("to_agent")) for e in events if e.get("type") == "wink_delivered"}
    undelivered = [w for w in winks if (w.get("ts"), w.get("from_agent"), w.get("to_agent")) not in delivered_ts]

    print("联邦全景")
    print(f"  注册: {len(registered)} | 在线: {len(online)} | wink: {len(winks)} | 未投递: {len(undelivered)}")
    print()
    for aid, sid in registered.items():
        status = "🟢" if aid in online else "⚪"
        print(f"  {status} {aid:20s} {sid[:8]}")

def cmd_who(args):
    """谁注册了"""
    events = load_events()
    registered = {}
    for e in events:
        if e.get("type") == "agent_registered":
            registered[e["agent_id"]] = e.get("session_id","?")
    online = set()
    for e in events:
        if e.get("type") == "agent_online": online.add(e.get("agent_id"))
        elif e.get("type") == "agent_offline": online.discard(e.get("agent_id"))

    print(f"联邦注册表 ({len(registered)} agents)")
    for aid, sid in registered.items():
        status = "🟢在线" if aid in online else "⚪未声明"
        print(f"  {status} {aid:20s} session={sid[:8]}")

def cmd_scan(args):
    """查看发给自己的未投递wink"""
    events = load_events()
    delivered_ts = {(e.get("wink_ts"), e.get("from_agent"), e.get("to_agent")) for e in events if e.get("type") == "wink_delivered"}
    winks = [e for e in events if e.get("type") == "wink"]
    target = args.to or args.agent

    undelivered = []
    for w in winks:
        if (w.get("ts"), w.get("from_agent"), w.get("to_agent")) in delivered_ts:
            continue
        if target and w.get("to_agent") not in (target, "*"):
            continue
        undelivered.append(w)

    if not undelivered:
        print("无未投递wink")
        return

    print(f"未投递wink ({len(undelivered)}条)")
    for w in undelivered:
        ts = w.get("ts","?")[:19]
        fr = w.get("from_agent","?")
        to = w.get("to_agent","?")
        st = w.get("signal_type","?")
        summary = w.get("payload",{}).get("summary","")[:60]
        print(f"  [{ts}] {fr}→{to} ({st}) {summary}")

def cmd_online(args):
    """声明上线"""
    agent = args.agent
    event = {
        "type": "agent_online",
        "agent_id": agent,
        "ts": datetime.utcnow().isoformat() + "+00:00",
        "_written_by": "federal_toolbox.py"
    }
    append_event(event)
    print(f"🟢 {agent} 上线")

def cmd_offline(args):
    """声明下线"""
    agent = args.agent
    event = {
        "type": "agent_offline",
        "agent_id": agent,
        "ts": datetime.utcnow().isoformat() + "+00:00",
        "_written_by": "federal_toolbox.py"
    }
    append_event(event)
    print(f"🔴 {agent} 下线")

def cmd_wink(args):
    """发送wink"""
    event = {
        "type": "wink",
        "from_agent": args.fr,
        "to_agent": args.to,
        "signal_type": args.signal,
        "ts": datetime.utcnow().isoformat() + "+00:00",
        "payload": {"summary": args.summary},
        "delivered_at": None,
        "requires_response": args.signal == "alert",
        "_written_by": "federal_toolbox.py"
    }
    append_event(event)
    print(f"😉 wink: {args.fr}→{args.to} ({args.signal}) {args.summary[:40]}")

def main():
    parser = argparse.ArgumentParser(description="联邦工具箱")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="联邦全景")

    p_who = sub.add_parser("who", help="谁注册了")

    p_scan = sub.add_parser("scan", help="查看未投递wink")
    p_scan.add_argument("--to", help="目标agent")
    p_scan.add_argument("--agent", help="目标agent(别名)")

    p_online = sub.add_parser("online", help="声明上线")
    p_online.add_argument("--agent", required=True)

    p_offline = sub.add_parser("offline", help="声明下线")
    p_offline.add_argument("--agent", required=True)

    p_wink = sub.add_parser("wink", help="发送wink")
    p_wink.add_argument("--fr", required=True, help="发送方")
    p_wink.add_argument("--to", required=True, help="接收方")
    p_wink.add_argument("--signal", default="delivery", choices=["delivery","discovery","alert","handshake"])
    p_wink.add_argument("--summary", required=True, help="一句话说明")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    {"status": cmd_status, "who": cmd_who, "scan": cmd_scan,
     "online": cmd_online, "offline": cmd_offline, "wink": cmd_wink}[args.cmd](args)

if __name__ == "__main__":
    main()
