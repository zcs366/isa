#!/usr/bin/env python3
"""
ISA Cognitive Data Schema v0.1
================================

ISA Project的认知数据格式标准。
定义了四个核心数据类型的JSON Schema:
  - BrainCard: Agent的卡片知识单元
  - DeltaCapsule: Δ胶囊语义记忆
  - Arbitration: Arbiter认知裁决记录
  - GoalState: Goal目标状态

版本: 0.1.0
更新: 2026-06-21
协议: MIT — 任何框架可自由实现
"""

# ── 版本号 ──
SCHEMA_VERSION = "0.1.0"

# ── 1. BrainCard — 卡片知识单元 ──
#
# 用途: Agent认知引擎的基本知识单元。
#       每个卡片代表一个独立话题/知识领域。
# 存储: ~/.hermes/isa/brain/{agent_id}/cards/{card_id}.json
# 生命周期: active → paused → archived(可恢复)
BRAIN_CARD_SCHEMA = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "$id": "isa://schemas/brain-card/v0.1",
    "title": "BrainCard",
    "description": "ISA Project卡片知识单元——Agent认知引擎的基本知识块",
    "type": "object",
    "required": ["card_id", "title", "status", "created", "keywords"],
    "properties": {
        "card_id": {
            "type": "string",
            "description": "唯一标识, kebab-case, 如'isa-wave-mechanics'",
            "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"
        },
        "title": {"type": "string", "description": "中文标题"},
        "status": {
            "type": "string",
            "enum": ["active", "paused", "archived"],
            "description": "active=活跃/参与话题匹配, paused=暂停/不匹配, archived=归档/历史"
        },
        "created": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601创建时间"
        },
        "last_updated": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601最后更新时间"
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "关键词标签, 用于dream()关联检测和话题匹配"
        },
        "summary": {
            "type": "string",
            "maxLength": 500,
            "description": "摘要——卡片核心内容的一两句话"
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date"},
                    "decision": {"type": "string"},
                    "context": {"type": "string"}
                }
            },
            "description": "关键决策记录"
        },
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date"},
                    "content": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["insight", "question", "reference", "todo"]
                    }
                }
            },
            "description": "洞察/问题/参考/待办"
        },
        "consciousness_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date-time"},
                    "thought": {"type": "string"}
                }
            },
            "description": "LLM写的意识笔记——随想/反思"
        }
    }
}

# ── 2. DeltaCapsule — 语义记忆胶囊 ──
#
# 用途: Δ胶囊记忆固化系统的语义向量单元。
#       每个capsule记录一次认知事件的语义位置。
# 存储: ~/.openllm/capsules/v06_{session_id}.json
# 版本: v06=可读文本, v07=语义向量
DELTA_CAPSULE_SCHEMA = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "$id": "isa://schemas/delta-capsule/v0.1",
    "title": "DeltaCapsule",
    "description": "Δ胶囊语义记忆单元——Agent认知事件的语义沉积",
    "type": "object",
    "required": ["session_id", "timestamp"],
    "properties": {
        "session_id": {
            "type": "string",
            "description": "会话/事件唯一标识, 如'dream-军师-2026-06-21T...'"
        },
        "timestamp": {
            "type": "number",
            "description": "Unix时间戳(秒)"
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "agent": {"type": "string"}
                }
            },
            "description": "决策记录"
        },
        "insights": {
            "type": "array",
            "items": {"type": "string"},
            "description": "洞察文本列表"
        },
        "outputs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "产出路径列表"
        },
        "unresolved": {
            "type": "array",
            "items": {"type": "string"},
            "description": "待解决问题"
        }
    }
}

# ── 3. Arbitration — 认知裁决记录 ──
#
# 用途: Arbiter认知仲裁层的裁决记录。
#       每次仲裁生成一条记录, 可回溯可审计。
# 存储: ~/.hermes/isa/arbiter/arbitrations.jsonl
# 格式: JSONL — 每行一条独立裁决
ARBITRATION_SCHEMA = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "$id": "isa://schemas/arbitration/v0.1",
    "title": "Arbitration",
    "description": "Arbiter认知仲裁裁决记录",
    "type": "object",
    "required": ["topic_a", "topic_b", "verdict", "arbitrated_at"],
    "properties": {
        "topic_a": {
            "type": "string",
            "description": "矛盾一方的话题/卡片ID"
        },
        "topic_b": {
            "type": "string",
            "description": "矛盾另一方的话题/卡片ID"
        },
        "verdict": {
            "type": "string",
            "enum": ["resolved", "contradiction", "stalemate"],
            "description": "resolved=可调和, contradiction=真矛盾, stalemate=证据不足"
        },
        "resolution": {
            "type": "string",
            "description": "裁决结果描述"
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "置信度 0-1"
        },
        "claim_count": {
            "type": "integer",
            "minimum": 1,
            "description": "涉及的claim数量"
        },
        "agents": {
            "type": "array",
            "items": {"type": "string"},
            "description": "相关Agent列表"
        },
        "arbitrated_at": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601仲裁时间"
        }
    }
}

# ── 4. GoalState — 目标状态记录 ──
#
# 用途: Goal目标层的目标状态持久化。
#       每个目标记录Agent的意图和进展。
# 存储: ~/.hermes/isa/goals/{agent_id}/goals.json
# 格式: JSON Object, 内含goal_id→Goal映射
GOAL_STATE_SCHEMA = {
    "$schema": "https://json-schema.org/draft-07/schema#",
    "$id": "isa://schemas/goal-state/v0.1",
    "title": "GoalState",
    "description": "Goal目标状态——Agent前额叶的意图记录",
    "type": "object",
    "required": ["agent_id", "updated", "goals"],
    "properties": {
        "agent_id": {
            "type": "string",
            "description": "Agent身份标识"
        },
        "updated": {
            "type": "string",
            "format": "date-time",
            "description": "最后更新时间"
        },
        "goals": {
            "type": "object",
            "additionalProperties:": False,
            "patternProperties": {
                "^[a-z0-9]+(-[a-z0-9]+)*$": {
                    "type": "object",
                    "required": ["goal_id", "title", "priority", "status"],
                    "properties": {
                        "goal_id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["high", "mid", "low"]
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "parent": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["active", "paused", "completed", "abandoned"]
                        },
                        "created": {"type": "string", "format": "date-time"},
                        "progress": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        },
                        "notes": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            },
            "description": "goal_id→Goal对象映射"
        }
    }
}


def validate(instance: dict, schema: dict) -> list[str]:
    """校验一个数据实例是否符合Schema。

    返回: 错误列表, 空列表=校验通过。
    """
    errors = []
    required = schema.get("required", [])
    for field in required:
        if field not in instance:
            errors.append(f"缺少必填字段: {field}")

    props = schema.get("properties", {})
    for field, definition in props.items():
        if field not in instance:
            continue
        value = instance[field]

        # type检查
        expected_type = definition.get("type")
        if expected_type == "string" and not isinstance(value, str):
            errors.append(f"{field}: 期望string, 实际{type(value).__name__}")
        elif expected_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"{field}: 期望number, 实际{type(value).__name__}")
        elif expected_type == "integer" and not isinstance(value, int):
            errors.append(f"{field}: 期望integer, 实际{type(value).__name__}")
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(f"{field}: 期望array, 实际{type(value).__name__}")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"{field}: 期望object, 实际{type(value).__name__}")

        # enum检查
        enum_values = definition.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"{field}: 值'{value}'不在允许枚举{enum_values}中")

        # minItems检查
        min_items = definition.get("minItems")
        if isinstance(value, list) and min_items and len(value) < min_items:
            errors.append(f"{field}: 最少{min_items}项, 实际{len(value)}")

    return errors


if __name__ == "__main__":
    import json
    import sys

    # CLI: validate一个JSON文件
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = json.load(f)
        schema_name = sys.argv[2] if len(sys.argv) > 2 else "brain_card"
        schemas = {
            "brain_card": BRAIN_CARD_SCHEMA,
            "capsule": DELTA_CAPSULE_SCHEMA,
            "arbitration": ARBITRATION_SCHEMA,
            "goal": GOAL_STATE_SCHEMA,
        }
        schema = schemas.get(schema_name)
        if not schema:
            print(f"未知schema: {schema_name}. 可选: {list(schemas.keys())}")
            sys.exit(1)
        errors = validate(data, schema)
        if errors:
            print(f"❌ {sys.argv[1]}: {len(errors)} 个错误")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"✅ {sys.argv[1]}: Schema校验通过")
    else:
        print(f"ISA Cognitive Data Schema v{SCHEMA_VERSION}")
        print(f"  4 schemas: brain_card, capsule, arbitration, goal")
        print(f"  用法: python3 {sys.argv[0]} <json文件> <schema名>")
