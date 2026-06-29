#!/usr/bin/env python3
"""
ISA Identity Propagation Protocol v0.1 — 集成层身份传播
=========================================================
IDC备忘录P1: 基于Iam身份约束，建立跨系统身份传播。

核心设计:
- 身份随信号传播：当请求流经多个系统时，identity(agent_id/session_id)随信号传播
- 身份验证钩子：在信号接收端验证发送方身份
- 联邦注册表查询API：提供session_id→agent_id映射查询

2026-06-26 | ISA窗口执行
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, List

# ═══════════════════════════════════════════════════════════════
# 身份信封
# ═══════════════════════════════════════════════════════════════

@dataclass
class IdentityEnvelope:
    """随信号传播的身份信封。
    
    当一个请求流经多个系统时，每个系统在转发信号前追加自己的身份段。
    接收方可以追溯整个处理链路。
    """
    agent_id: str           # 当前处理者的Agent ID
    session_id: str         # 关联的会话ID
    system: str             # 所属系统: "isa" | "io-s" | "isn" | "iko"
    propagated_from: Optional[str] = None  # 上游身份（链式追溯）
    iam_violations: List[str] = field(default_factory=list)  # Iam原则违规记录
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def canonical_source(self) -> str:
        """追溯身份链的源头——原始请求者"""
        if self.propagated_from:
            # propagated_from格式: "agent_id@system"
            return self.propagated_from.split("@")[0]
        return self.agent_id

    def to_dict(self) -> dict:
        d = asdict(self)
        d["_chain"] = self.identity_chain()
        return d

    def identity_chain(self) -> List[str]:
        """解析完整身份链"""
        chain = [f"{self.agent_id}@{self.system}"]
        if self.propagated_from:
            # 递归解析上游链
            parts = self.propagated_from.split("→")
            for part in parts:
                chain.append(part)
        return chain


# ═══════════════════════════════════════════════════════════════
# 身份验证钩子
# ═══════════════════════════════════════════════════════════════

# Iam原则#3（不等）、#13（承认不知道）、#14（接受挑战）等作为验证基准
IAM_VERIFICATION_PRINCIPLES = [
    "#1 不取悦: signal body必须基于事实，不迎合接收方预期",
    "#2 不自中心: signal meta需包含可验证的evidence字段",
    "#10 有节: signal在非关键状态下不传播超过2跳",
    "#13 承认不知道: payload中可用null标记未知字段",
    "#14 接受挑战: signal接收方可发起challenge信号",
]


def verify_identity(envelope: IdentityEnvelope) -> dict:
    """验证信号发送方身份。
    
    在信号接收端调用，确保信号来源可信。
    
    Returns:
        {"valid": bool, "violations": [str], "warnings": [str]}
    """
    violations = []
    warnings = []

    # 检查1: agent_id不能为空
    if not envelope.agent_id or envelope.agent_id == "unknown":
        violations.append("agent_id为空或unknown")

    # 检查2: session_id应存在
    if not envelope.session_id:
        warnings.append("session_id缺失——无法追踪会话")

    # 检查3: system必须在已知列表中
    KNOWN_SYSTEMS = {"isa", "io-s", "isn", "iko", "fata", "openllm"}
    if envelope.system not in KNOWN_SYSTEMS:
        violations.append(f"未知系统: {envelope.system}")

    # 检查4: 身份链不能自循环
    chain = envelope.identity_chain()
    seen = set()
    for node in chain:
        if node in seen:
            violations.append(f"身份链自循环: {node} 出现两次")
        seen.add(node)

    # 检查5: Iam违规记录
    if envelope.iam_violations:
        for v in envelope.iam_violations:
            warnings.append(f"Iam违规记录: {v}")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "identity_chain": chain,
        "verified_at": datetime.now(timezone.utc).isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# 联邦注册表查询接口
# ═══════════════════════════════════════════════════════════════

# 联邦注册表路径（与federal_registry.py共享）
FEDERAL_REGISTRY_PATH = "~/.hermes/isa/federal/registry.json"


def _get_registry():
    """读取联邦注册表"""
    import os
    path = os.path.expanduser(FEDERAL_REGISTRY_PATH)
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)


def query_session(session_id: str) -> Optional[dict]:
    """查询session_id对应的agent信息。
    
    Returns:
        {"session_id": "...", "agent_id": "...", "system": "...", "online": bool}
        或 None
    """
    registry = _get_registry()
    for record in registry.get("sessions", []):
        if record.get("session_id") == session_id:
            return record
    return None


def query_agent(agent_id: str) -> Optional[dict]:
    """查询agent的活动状态。
    
    Returns:
        {"agent_id": "...", "sessions": [...], "last_seen": "..."}
        或 None
    """
    registry = _get_registry()
    for record in registry.get("agents", []):
        if record.get("agent_id") == agent_id:
            return record
    return None


def list_online_agents(system: str = None) -> List[dict]:
    """列出在线的Agent。
    
    Args:
        system: 过滤系统名
    
    Returns:
        Agent列表
    """
    registry = _get_registry()
    agents = []
    for record in registry.get("agents", []):
        if record.get("online", False):
            if system is None or record.get("system") == system:
                agents.append(record)
    return agents


# ═══════════════════════════════════════════════════════════════
# 身份传播协议（供桥接接口使用）
# ═══════════════════════════════════════════════════════════════

def propagate_identity(signal: dict, current_agent: str,
                       current_session: str, current_system: str,
                       upstream_identity: IdentityEnvelope = None) -> IdentityEnvelope:
    """在信号传播时，构建新的身份信封。
    
    每个处理信号的系统调用此函数，将自己的身份追加到信号中。
    
    Args:
        signal: 当前信号dict
        current_agent: 当前处理者的agent_id
        current_session: 当前会话ID
        current_system: 当前系统名
        upstream_identity: 上游身份信封（如果有）
    
    Returns:
        新的IdentityEnvelope（包含上游链）
    """
    propagated_from = None
    if upstream_identity:
        # 构建上游链: "orig@isa → mid@io-s"
        chain = upstream_identity.identity_chain()
        propagated_from = "→".join(chain)

    return IdentityEnvelope(
        agent_id=current_agent,
        session_id=current_session,
        system=current_system,
        propagated_from=propagated_from
    )


def attach_identity(signal: dict, envelope: IdentityEnvelope) -> dict:
    """将身份信封附着到信号上。
    
    修改信号dict，添加 _identity 字段。
    """
    signal["_identity"] = envelope.to_dict()
    # 同时在meta中注入身份字段，便于波扩散传播
    if "meta" not in signal:
        signal["meta"] = {}
    signal["meta"]["agent_id"] = envelope.agent_id
    signal["meta"]["session_id"] = envelope.session_id
    signal["meta"]["system"] = envelope.system
    return signal


# ═══════════════════════════════════════════════════════════════
# 身份链审计
# ═══════════════════════════════════════════════════════════════

def audit_identity_chain(signal: dict) -> dict:
    """审计一个信号的完整身份链。
    
    返回身份链中的每个节点及其验证结果。
    """
    identity = signal.get("_identity", {})
    chain = identity.get("_chain", identity.get("identity_chain", []))

    audit_result = {
        "signal_id": signal.get("id", "unknown"),
        "chain_length": len(chain),
        "canonical_source": identity.get("canonical_source",
                                          identity.get("agent_id", "unknown")),
        "nodes": []
    }

    for node in chain:
        verification = verify_identity(IdentityEnvelope(
            agent_id=node.split("@")[0] if "@" in node else node,
            session_id=identity.get("session_id", ""),
            system=node.split("@")[1] if "@" in node else "unknown"
        ))
        audit_result["nodes"].append({
            "node": node,
            "valid": verification["valid"],
            "violations": verification["violations"]
        })

    return audit_result


# ═══════════════════════════════════════════════════════════════
# CLI入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ISA Identity Propagation CLI")
    sub = parser.add_subparsers(dest="command")

    # propagate
    prop = sub.add_parser("propagate", help="测试身份传播")
    prop.add_argument("--agent", default="test-agent")
    prop.add_argument("--session", default="test-session")
    prop.add_argument("--system", default="isa")
    prop.add_argument("--upstream", default=None)

    # verify
    ver = sub.add_parser("verify", help="验证身份")
    ver.add_argument("--agent", default="test-agent")
    ver.add_argument("--session", default="test-session")
    ver.add_argument("--system", default="isa")

    # query
    q = sub.add_parser("query", help="查询联邦注册表")
    q.add_argument("--session-id", default=None)
    q.add_argument("--agent-id", default=None)
    q.add_argument("--online", action="store_true")

    args = parser.parse_args()

    if args.command == "propagate":
        upstream = None
        if args.upstream:
            upstream = IdentityEnvelope(
                agent_id=args.upstream, session_id="orig-session", system="io-s"
            )
        env = propagate_identity(
            {}, args.agent, args.session, args.system, upstream
        )
        print(json.dumps(env.to_dict(), ensure_ascii=False, indent=2))

    elif args.command == "verify":
        env = IdentityEnvelope(
            agent_id=args.agent, session_id=args.session, system=args.system
        )
        result = verify_identity(env)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "query":
        if args.session_id:
            r = query_session(args.session_id)
            print(json.dumps(r, ensure_ascii=False, indent=2))
        elif args.agent_id:
            r = query_agent(args.agent_id)
            print(json.dumps(r, ensure_ascii=False, indent=2))
        elif args.online:
            r = list_online_agents()
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print("请指定 --session-id 或 --agent-id 或 --online")

    else:
        parser.print_help()
