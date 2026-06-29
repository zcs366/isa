#!/usr/bin/env python3
"""
SA静默状态机 — 联邦法第4号实现

💬 ACTIVE → (declaration wink) → 🔵 DECLARED_SILENT → (超时) → 🔴 ABNORMAL
💬 ACTIVE → (静默超时无declaration) → 🔴 ABNORMAL → heartbeat探测
任意状态 → (agent_offline) → ⚫ OFFLINE

用法:
  python3 silence_state.py                    # 运行测试
  python3 silence_state.py scan               # 扫描RECALL检查所有SA状态
  python3 silence_state.py check <agent_id>   # 检查单个SA
"""

import json, os, sys
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict

RECALL = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")

class SilenceState(Enum):
    ACTIVE = "💬"
    DECLARED_SILENT = "🔵"
    ABNORMAL = "🔴"
    OFFLINE = "⚫"
    UNKNOWN = "⚪"

class SilenceStateMachine:
    """单个SA的静默状态机"""

    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.state = SilenceState.UNKNOWN
        self.last_wink = None
        self.last_online = None
        self.declaration = None  # {until: datetime, reason: str}
        self.last_heartbeat = None

    def on_wink(self, ts=None):
        """收到或发送wink → 活跃"""
        self.state = SilenceState.ACTIVE
        self.last_wink = ts or datetime.now(timezone.utc)
        self.declaration = None

    def on_online(self, ts=None):
        """声明上线"""
        self.state = SilenceState.ACTIVE
        self.last_online = ts or datetime.now(timezone.utc)

    def on_offline(self, ts=None):
        """声明下线"""
        self.state = SilenceState.OFFLINE

    def on_declaration(self, duration_hours, reason="", ts=None):
        """声明静默"""
        self.state = SilenceState.DECLARED_SILENT
        now = ts or datetime.now(timezone.utc)
        self.declaration = {
            "until": now + timedelta(hours=duration_hours),
            "reason": reason
        }

    def check(self, now=None):
        """
        检查当前状态。返回 (state, alert: bool, reason: str)
        仅在异常时 alert=True。
        """
        now = now or datetime.now(timezone.utc)

        # 已下线
        if self.state == SilenceState.OFFLINE:
            return self.state, False, ""

        # 已声明静默：检查是否超时
        if self.state == SilenceState.DECLARED_SILENT:
            if self.declaration and now > self.declaration["until"]:
                # 声明期满
                if self.last_wink and (now - self.last_wink) < timedelta(hours=1):
                    self.state = SilenceState.ACTIVE
                    self.declaration = None
                    return self.state, False, "声明期满·自动恢复活跃"
                else:
                    self.state = SilenceState.ABNORMAL
                    return self.state, True, f"声明期满但无恢复信号·最后wink={self.last_wink}"
            return self.state, False, f"静默中·until={self.declaration['until'] if self.declaration else '?'}"

        # 活跃：检查是否超时无wink
        if self.state == SilenceState.ACTIVE:
            if self.last_wink and (now - self.last_wink) > timedelta(hours=6):
                self.state = SilenceState.ABNORMAL
                return self.state, True, f"活跃超时·最后wink={self.last_wink}"
            return self.state, False, ""

        # 未知状态
        if self.last_wink and (now - self.last_wink) > timedelta(hours=6):
            self.state = SilenceState.ABNORMAL
            return self.state, True, f"未知状态超时·最后wink={self.last_wink}"

        return self.state, False, ""


def load_events():
    """加载RECALL事件"""
    events = []
    with open(RECALL) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except:
                pass
    return events


def build_state_machines(events):
    """从RECALL事件构建所有SA的状态机"""
    machines = {}

    def get_machine(agent_id):
        if agent_id not in machines:
            machines[agent_id] = SilenceStateMachine(agent_id)
        return machines[agent_id]

    for e in events:
        t = e.get("type")
        ts_str = e.get("ts") or e.get("_timestamp") or e.get("registered_at")
        ts = None
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except:
                pass

        if t == "agent_registered":
            get_machine(e["agent_id"])
        elif t == "federal_register":
            get_machine(e["agent_id"])
        elif t == "agent_online":
            get_machine(e["agent_id"]).on_online(ts)
        elif t == "agent_offline":
            get_machine(e["agent_id"]).on_offline(ts)
        elif t == "wink":
            get_machine(e["from_agent"]).on_wink(ts)
            if e.get("to_agent") and e["to_agent"] != "*":
                get_machine(e["to_agent"]).on_wink(ts)
        elif t == "declaration":
            m = get_machine(e["agent_id"])
            duration = e.get("duration_hours", 48)
            reason = e.get("reason", "")
            m.on_declaration(duration, reason, ts)
        elif t == "agent_offline":
            get_machine(e["agent_id"]).on_offline(ts)
        elif t == "heartbeat":
            m = get_machine(e["agent_id"])
            m.last_heartbeat = ts
            m.last_wink = ts  # heartbeat也算活动信号

    return machines


def cmd_scan(args):
    """扫描RECALL检查所有SA状态"""
    events = load_events()
    machines = build_state_machines(events)

    print(f"联邦静默状态扫描 ({len(machines)} agents)")
    print("=" * 50)

    # SA名称归一化映射（中英文双名→统一英文ID）
    NORMALIZE = {
        "搜神": "soushen",
    }

    alerts = []
    for agent_id, m in sorted(machines.items()):
        # 归一化显示名
        display_id = NORMALIZE.get(agent_id, agent_id)
        if display_id != agent_id:
            continue  # 中文名跳过，由英文名统一显示
        state, alert, reason = m.check()
        icon = state.value
        line = f"  {icon} {display_id:20s}"
        if m.last_wink:
            line += f"  last_wink={m.last_wink.strftime('%m-%d %H:%M')}"
        if m.declaration:
            line += f"  until={m.declaration['until'].strftime('%m-%d %H:%M')}"
        print(line)
        if alert:
            alerts.append((agent_id, reason))

    if alerts:
        print(f"\n⚠️  异常 ({len(alerts)}):")
        for aid, reason in alerts:
            print(f"  🔴 {aid}: {reason}")
    else:
        print(f"\n✅ 无异常")

    return alerts


def cmd_check(args):
    """检查单个SA"""
    events = load_events()
    machines = build_state_machines(events)
    agent_id = args.agent

    if agent_id not in machines:
        print(f"❌ {agent_id} 未在RECALL中找到")
        return

    m = machines[agent_id]
    state, alert, reason = m.check()

    print(f"SA: {agent_id}")
    print(f"  状态: {state.value} {state.name}")
    print(f"  最后wink: {m.last_wink}")
    print(f"  最后online: {m.last_online}")
    print(f"  声明: {m.declaration}")
    if alert:
        print(f"  ⚠️  告警: {reason}")


def test():
    """单元测试"""
    print("运行静默状态机测试...")

    # 测试1: 基本状态转换
    m = SilenceStateMachine("test_agent")
    assert m.state == SilenceState.UNKNOWN

    m.on_online()
    assert m.state == SilenceState.ACTIVE

    m.on_declaration(48, "长程任务")
    assert m.state == SilenceState.DECLARED_SILENT

    # 测试2: 声明超时 → 异常
    m2 = SilenceStateMachine("test_timeout")
    m2.on_online()
    past = datetime.now(timezone.utc) - timedelta(hours=10)
    m2.on_declaration(2, "短静默", past)
    state, alert, reason = m2.check()
    assert state == SilenceState.ABNORMAL
    assert alert == True

    # 测试3: 活跃超时 → 异常
    m3 = SilenceStateMachine("test_active_timeout")
    m3.on_wink(datetime.now(timezone.utc) - timedelta(hours=10))
    state, alert, reason = m3.check()
    assert state == SilenceState.ABNORMAL
    assert alert == True

    # 测试4: 正常活跃 → 无告警
    m4 = SilenceStateMachine("test_active_ok")
    m4.on_wink()
    state, alert, reason = m4.check()
    assert state == SilenceState.ACTIVE
    assert alert == False

    # 测试5: 下线
    m5 = SilenceStateMachine("test_offline")
    m5.on_online()
    m5.on_offline()
    assert m5.state == SilenceState.OFFLINE

    print("✅ 全部测试通过")


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "scan":
            cmd_scan(None)
        elif cmd == "check":
            if len(sys.argv) < 3:
                print("用法: silence_state.py check <agent_id>")
                sys.exit(1)
            class Args:
                agent = sys.argv[2]
            cmd_check(Args())
        elif cmd == "test":
            test()
        else:
            print(f"未知命令: {cmd}")
            print("用法: silence_state.py [scan|check <agent_id>|test]")
    else:
        test()
        print()
        cmd_scan(None)


if __name__ == "__main__":
    main()
