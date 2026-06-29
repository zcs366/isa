#!/usr/bin/env python3
"""
ISA Signal Registry v0.1 — 波扩散升级为统一信号总线
=====================================================
IDC备忘录P0: 让IO-S、ISN、IKO的事件都通过ISA波扩散传播。

核心设计:
- 信号类型: io-s.governance / isn.skill-exec / iko.publish
- 路由规则: 按前缀自动转发到目标系统
- 桥接接口: signal_send/recv/query 标准接口

2026-06-26 | ISA窗口执行
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, List, Callable

# ═══════════════════════════════════════════════════════════════
# 信号类型注册表
# ═══════════════════════════════════════════════════════════════

@dataclass
class SignalType:
    """一种已注册的系统间信号类型"""
    type_name: str          # 如 "io-s.governance"
    namespace: str          # 所属系统命名空间: "io-s" | "isn" | "iko"
    category: str           # 信号类别: governance | skill-exec | publish
    description: str        # 描述
    target_system: str      # 自动转发到的目标系统
    routing_priority: int = 0  # 路由优先级，0最低
    meta_schema: Optional[Dict] = None  # payload schema

# 信号类型注册表（注册即生效）
SIGNAL_TYPES: Dict[str, SignalType] = {
    # ── IO-S 治理信号 ──
    "io-s.governance": SignalType(
        type_name="io-s.governance",
        namespace="io-s",
        category="governance",
        description="IO-S治理事件：cap_check结果、权限变更、syscall审计",
        target_system="io-s",
        routing_priority=10,
        meta_schema={
            "event": "cap_check | cap_change | syscall_audit | policy_update",
            "pid": "str",
            "resource": "str",
            "operation": "str",
            "result": "allowed | denied",
            "audit_id": "str"
        }
    ),
    "io-s.governance.cap-check": SignalType(
        type_name="io-s.governance.cap-check",
        namespace="io-s",
        category="governance",
        description="IO-S权限检查结果广播",
        target_system="io-s",
        routing_priority=10,
        meta_schema={
            "event": "cap_check",
            "pid": "str",
            "resource": "str",
            "operation": "str",
            "result": "allowed | denied",
            "reason": "str (optional)"
        }
    ),
    "io-s.governance.policy-update": SignalType(
        type_name="io-s.governance.policy-update",
        namespace="io-s",
        category="governance",
        description="IO-S权限策略变更通知",
        target_system="all",  # 策略变更→通知所有系统
        routing_priority=9,
        meta_schema={
            "event": "policy_update",
            "policy_field": "str",
            "old_value": "str",
            "new_value": "str",
            "effective_immediately": "bool"
        }
    ),

    # ── ISN 技能执行信号 ──
    "isn.skill-exec": SignalType(
        type_name="isn.skill-exec",
        namespace="isn",
        category="skill-exec",
        description="ISN技能执行事件：技能调用、结果返回、错误",
        target_system="isn",
        routing_priority=5,
        meta_schema={
            "event": "skill_call | skill_result | skill_error | skill_created | skill_updated",
            "skill_name": "str",
            "caller_agent": "str",
            "execution_time_ms": "int (optional)",
            "result_summary": "str (optional)",
            "error": "str (optional)"
        }
    ),
    "isn.skill-exec.created": SignalType(
        type_name="isn.skill-exec.created",
        namespace="isn",
        category="skill-exec",
        description="ISN新技能创建通知",
        target_system="all",  # 新技能→通知所有系统
        routing_priority=5,
        meta_schema={
            "event": "skill_created",
            "skill_name": "str",
            "category": "str",
            "llm_audit": "str | null"
        }
    ),
    "isn.skill-exec.called": SignalType(
        type_name="isn.skill-exec.called",
        namespace="isn",
        category="skill-exec",
        description="ISN技能被调用",
        target_system="isn",
        routing_priority=3,
        meta_schema={
            "event": "skill_call",
            "skill_name": "str",
            "caller_agent": "str",
            "args_summary": "str",
            "execution_time_ms": "int"
        }
    ),
    "isn.skill-exec.error": SignalType(
        type_name="isn.skill-exec.error",
        namespace="isn",
        category="skill-exec",
        description="ISN技能执行错误",
        target_system="all",  # 错误→通知所有系统
        routing_priority=8,
        meta_schema={
            "event": "skill_error",
            "skill_name": "str",
            "error_type": "str",
            "error_message": "str"
        }
    ),

    # ── IKO 发布信号 ──
    "iko.publish": SignalType(
        type_name="iko.publish",
        namespace="iko",
        category="publish",
        description="IKO发布事件：内容生成、发布确认、渠道状态",
        target_system="iko",
        routing_priority=1,
        meta_schema={
            "event": "asset_created | published | publish_confirmed | publish_failed | channel_status",
            "asset_id": "str",
            "asset_type": "str",
            "channel": "str",
            "status": "str",
            "url": "str (optional)",
            "error": "str (optional)"
        }
    ),
    "iko.publish.created": SignalType(
        type_name="iko.publish.created",
        namespace="iko",
        category="publish",
        description="IKO新资产创建（等待发布）",
        target_system="all",  # 新资产→通知所有系统
        routing_priority=2,
        meta_schema={
            "event": "asset_created",
            "asset_id": "str",
            "asset_type": "str",
            "channels": "list[str]",
            "manifest_path": "str"
        }
    ),
    "iko.publish.confirmed": SignalType(
        type_name="iko.publish.confirmed",
        namespace="iko",
        category="publish",
        description="IKO发布已确认",
        target_system="all",
        routing_priority=2,
        meta_schema={
            "event": "publish_confirmed",
            "asset_id": "str",
            "channels_published": "list[str]",
            "urls": "dict[str, str]"
        }
    ),
}

# ═══════════════════════════════════════════════════════════════
# 路由规则引擎
# ═══════════════════════════════════════════════════════════════

@dataclass
class RoutingRule:
    """信号路由规则"""
    prefix: str             # 匹配前缀，如 "io-s."
    target_system: str      # 目标系统
    priority: int = 0       # 优先级，数值越大越先匹配
    auto_ack: bool = False  # 是否需要自动确认
    ttl_seconds: int = 300  # 信号生存时间

# 路由规则表（按优先级降序排列）
ROUTING_RULES: List[RoutingRule] = [
    # 精确匹配优先
    RoutingRule(prefix="io-s.governance.policy-update", target_system="all", priority=9),
    RoutingRule(prefix="isn.skill-exec.error", target_system="all", priority=8),
    RoutingRule(prefix="io-s.governance", target_system="io-s", priority=10),
    RoutingRule(prefix="isn.skill-exec.created", target_system="all", priority=5),
    RoutingRule(prefix="isn.skill-exec", target_system="isn", priority=5),
    RoutingRule(prefix="iko.publish.created", target_system="all", priority=2),
    RoutingRule(prefix="iko.publish.confirmed", target_system="all", priority=2),
    RoutingRule(prefix="iko.publish", target_system="iko", priority=1),
]

# ═══════════════════════════════════════════════════════════════
# 信号桥接接口
# ═══════════════════════════════════════════════════════════════

def resolve_route(signal_type: str) -> Optional[RoutingRule]:
    """解析信号类型的路由目标。
    
    Args:
        signal_type: 信号类型，如 "io-s.governance.cap-check"
    
    Returns:
        匹配的RoutingRule，或None
    """
    # 按优先级降序遍历规则
    for rule in sorted(ROUTING_RULES, key=lambda r: -r.priority):
        if signal_type.startswith(rule.prefix):
            return rule
    return None


def get_signal_schema(signal_type: str) -> Optional[SignalType]:
    """获取信号类型的schema定义。
    
    Args:
        signal_type: 信号类型
    
    Returns:
        SignalType或None
    """
    # 精确匹配
    if signal_type in SIGNAL_TYPES:
        return SIGNAL_TYPES[signal_type]
    
    # 前缀匹配（找最具体的）
    best = None
    best_len = 0
    for st_name, st_def in SIGNAL_TYPES.items():
        if signal_type.startswith(st_name) and len(st_name) > best_len:
            best = st_def
            best_len = len(st_name)
    return best


def register_signal_type(type_name: str, namespace: str, category: str,
                         description: str, target_system: str,
                         routing_priority: int = 0,
                         meta_schema: Dict = None) -> SignalType:
    """动态注册新的信号类型（运行时扩展）。
    
    Args:
        type_name: 信号类型名，如 "io-s.governance.audit"
        namespace: 命名空间
        category: 类别
        description: 描述
        target_system: 目标系统
        routing_priority: 路由优先级
        meta_schema: payload schema
    
    Returns:
        新注册的SignalType
    """
    st = SignalType(
        type_name=type_name,
        namespace=namespace,
        category=category,
        description=description,
        target_system=target_system,
        routing_priority=routing_priority,
        meta_schema=meta_schema
    )
    SIGNAL_TYPES[type_name] = st
    return st


def list_signal_types(namespace: str = None) -> List[SignalType]:
    """列出所有已注册的信号类型。
    
    Args:
        namespace: 过滤指定命名空间
    
    Returns:
        SignalType列表
    """
    if namespace:
        return [st for st in SIGNAL_TYPES.values() if st.namespace == namespace]
    return list(SIGNAL_TYPES.values())


def list_routing_rules(target_system: str = None) -> List[RoutingRule]:
    """列出所有路由规则。
    
    Args:
        target_system: 过滤目标系统
    
    Returns:
        RoutingRule列表
    """
    if target_system:
        return [r for r in ROUTING_RULES if r.target_system == target_system]
    return list(ROUTING_RULES)


# ═══════════════════════════════════════════════════════════════
# 桥接接口（供其他系统调用）
# ═══════════════════════════════════════════════════════════════

def bridge_signal_send(to: str, signal_type: str, payload: dict,
                       source_agent: str = "unknown",
                       importance: float = 0.5) -> dict:
    """发送信号到ISA信号总线。
    
    这是其他系统（IO-S/ISN/IKO）调用ISA的唯一入口。
    
    Args:
        to: 目标系统（"io-s" | "isn" | "iko" | "all"）
        signal_type: 信号类型（必须是已注册的类型）
        payload: 信号载荷
        source_agent: 发送方agent标识
        importance: 重要性（≥0.4触发波扩散）
    
    Returns:
        {"status": "accepted" | "rejected", "signal_id": "...", "route": "..."}
    """
    # 1. 验证信号类型
    schema = get_signal_schema(signal_type)
    if not schema:
        return {
            "status": "rejected",
            "reason": f"未知信号类型: {signal_type}。可用类型: {list(SIGNAL_TYPES.keys())}"
        }
    
    # 2. 验证payload schema
    if schema.meta_schema:
        required_event = schema.meta_schema.get("event")
        if required_event and "event" in payload:
            valid_events = [e.strip() for e in required_event.split("|")]
            if payload.get("event") not in valid_events:
                return {
                    "status": "rejected",
                    "reason": f"无效event: {payload['event']}。有效值: {valid_events}"
                }
    
    # 3. 解析路由
    route = resolve_route(signal_type)
    if route and route.target_system == "all" and to != "all":
        pass  # 发送方可以覆盖路由
    
    # 4. 构建ISA信号
    import uuid
    from datetime import datetime, timezone
    
    signal_id = f"sys-{uuid.uuid4().hex[:12]}"
    
    isa_signal = {
        "type": "message",
        "subtype": signal_type,
        "source": source_agent,
        "target": to,
        "body": json.dumps(payload, ensure_ascii=False),
        "id": signal_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": "systems",
        "meta": {
            "importance": importance,
            "signal_type": signal_type,
            "namespace": schema.namespace,
            "route_target": route.target_system if route else to
        }
    }
    
    return {
        "status": "accepted",
        "signal_id": signal_id,
        "route": route.target_system if route else to,
        "signal": isa_signal  # 可直接emit到ISA Gateway
    }


def bridge_signal_recv(system: str = None, signal_type: str = None,
                        limit: int = 20, filter_by: dict = None) -> list[dict]:
    """查询已接收的信号。
    
    Args:
        system: 过滤系统名（"io-s" | "isn" | "iko"）
        signal_type: 过滤信号类型
        limit: 返回数量
        filter_by: 额外过滤条件
    
    Returns:
        信号列表
    """
    types = []
    if system:
        types = [st.type_name for st in list_signal_types(namespace=system)]
    elif signal_type:
        types = [signal_type]
    
    return {
        "status": "query",
        "matched_types": types,
        "limit": limit,
        "signals": []  # 由SignalGraph.retrieve()填充
    }


def bridge_signal_query(signal_type: str, window: str = "24h",
                         limit: int = 50) -> dict:
    """查询信号历史。
    
    Args:
        signal_type: 信号类型
        window: 时间窗口（"1h" | "24h" | "7d"）
        limit: 返回数量
    
    Returns:
        查询结果
    """
    return {
        "status": "query",
        "signal_type": signal_type,
        "window": window,
        "limit": limit,
        "count": 0,
        "signals": []  # 由SignalGraph.retrieve()填充
    }


# ═══════════════════════════════════════════════════════════════
# 注册表摘要（供其他窗口查阅）
# ═══════════════════════════════════════════════════════════════

def registry_summary() -> dict:
    """生成信号注册表摘要。
    
    返回一个字典，供其他系统窗口查阅ISA支持哪些信号类型和路由。
    """
    return {
        "version": "0.1",
        "registered_signal_count": len(SIGNAL_TYPES),
        "routing_rule_count": len(ROUTING_RULES),
        "signal_types": {
            st.type_name: {
                "namespace": st.namespace,
                "category": st.category,
                "description": st.description,
                "routing_priority": st.routing_priority,
                "target_system": st.target_system
            }
            for st in sorted(SIGNAL_TYPES.values(),
                             key=lambda x: f"{x.namespace}.{x.routing_priority}")
        },
        "routing_rules": [
            {
                "prefix": r.prefix,
                "target_system": r.target_system,
                "priority": r.priority
            }
            for r in sorted(ROUTING_RULES, key=lambda x: -x.priority)
        ]
    }


# ═══════════════════════════════════════════════════════════════
# CLI入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ISA Signal Registry CLI")
    sub = parser.add_subparsers(dest="command")

    # list-types
    sub.add_parser("list-types", help="列出所有已注册信号类型")

    # list-routes
    sub.add_parser("list-routes", help="列出所有路由规则")

    # summary
    sub.add_parser("summary", help="生成注册表摘要JSON")

    # send（供测试）
    send_p = sub.add_parser("send", help="发送信号（通过桥接接口）")
    send_p.add_argument("--to", required=True, help="目标系统")
    send_p.add_argument("--type", dest="signal_type", required=True, help="信号类型")
    send_p.add_argument("--payload", required=True, help="JSON payload")
    send_p.add_argument("--source", default="cli", help="发送方标识")

    # recv（供测试）
    recv_p = sub.add_parser("recv", help="查询信号类型")
    recv_p.add_argument("--system", default=None)
    recv_p.add_argument("--type", dest="signal_type", default=None)

    # register
    reg_p = sub.add_parser("register", help="动态注册新信号类型")
    reg_p.add_argument("--type-name", required=True)
    reg_p.add_argument("--namespace", required=True)
    reg_p.add_argument("--category", required=True)
    reg_p.add_argument("--description", required=True)
    reg_p.add_argument("--target-system", required=True)
    reg_p.add_argument("--priority", type=int, default=0)

    args = parser.parse_args()

    if args.command == "list-types":
        for st in sorted(SIGNAL_TYPES.values(),
                         key=lambda x: f"{x.namespace}.{x.routing_priority}"):
            print(f"  {st.type_name}")
            print(f"    → {st.target_system} (P{st.routing_priority}) {st.description}")
            print()
    elif args.command == "list-routes":
        for r in sorted(ROUTING_RULES, key=lambda x: -x.priority):
            print(f"  P{r.priority}: {r.prefix}* → {r.target_system}")
    elif args.command == "summary":
        print(json.dumps(registry_summary(), ensure_ascii=False, indent=2))
    elif args.command == "send":
        payload = json.loads(args.payload)
        result = bridge_signal_send(args.to, args.signal_type, payload, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "send":
        payload = json.loads(args.payload)
        result = bridge_signal_send(args.to, args.signal_type, payload, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "recv":
        result = bridge_signal_recv(system=args.system, signal_type=args.signal_type)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "register":
        st = register_signal_type(
            args.type_name, args.namespace, args.category,
            args.description, args.target_system, args.priority
        )
        print(f"✅ 已注册: {st.type_name} → {st.target_system}")
    else:
        parser.print_help()
