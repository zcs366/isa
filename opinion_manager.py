#!/usr/bin/env python3
"""
ISA opinion_manager.py — 认知预期结果 Schema 管理器
===================================================

定位：
  ISA 认知层的一部分。负责定义和导出"什么是一个好结果"的标准——
  这是 ISA 对 IO-S 的唯一依赖接口。

职责：
  - 定义 task_type 枚举（第一版硬编码，后续从 opinion 学习）
  - 为每个 task_type 提供 expected_result_schema()
  - 提供 verify 结果接收接口（Day 2 后 belief_update 对接）

设计原则：
  先硬编码，后从 opinion 学习。
  Day 1 先硬编码 8 个 task_type 的 schema，
  等 IO-S verify 跑起来后，再用 belief_update 学习 refine。

接口：
  expected_result_schema(task_type: str) -> dict
    - IO-S verify 钩子调用此接口获取验证标准
    - 返回 required（必须满足）和 forbidden（禁止出现）

版本: 0.1.0
创建: 2026-06-29
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("isa.opinion_manager")

# ── 版本号 ──
OPINION_SCHEMA_VERSION = "0.1.0"

# ── TaskType 枚举（第一版，逐步扩展） ──
TASK_TYPES = [
    "code_generation",      # 生代码
    "code_review",          # 审代码
    "research",             # 研究/分析
    "tool_call",            # 工具调用
    "documentation",        # 写文档
    "architecture_design",  # 架构设计
    "planning",             # 规划
    "debugging",            # 调试
]

# ── task_type 分类 ──
CODE_TYPES = {"code_generation", "code_review", "debugging"}
KNOWLEDGE_TYPES = {"research", "documentation", "architecture_design"}
ACTION_TYPES = {"tool_call", "planning"}


# ════════════════════════════════════════════════════════
# 硬编码 Schema 定义（Day 1 版本）
# 后续版本将从 opinion → belief_update 学习 refine
# ════════════════════════════════════════════════════════

def _build_code_generation() -> dict:
    """代码生成的预期结果标准。"""
    return {
        "task_type": "code_generation",
        "required": [
            "output_parsable",
            "no_syntax_error",
            "covers_main_logic",
        ],
        "forbidden": [
            "hardcoded_secrets",
            "shell_injection_patterns",
            "unbounded_recursion",
        ],
        "quality_gates": [
            {"gate": "has_test", "severity": "warn"},
            {"gate": "has_error_handling", "severity": "require"},
            {"gate": "docstring_present", "severity": "warn"},
        ],
        "opinion_sources": [],
    }


def _build_code_review() -> dict:
    """代码审查的预期结果标准。"""
    return {
        "task_type": "code_review",
        "required": [
            "output_parsable",
            "covers_main_logic",
            "identifies_bugs_or_missed_cases",
        ],
        "forbidden": [
            "vague_approval_without_evidence",
            "ignored_security_concerns",
        ],
        "quality_gates": [
            {"gate": "has_line_specific_comments", "severity": "require"},
            {"gate": "prioritizes_findings", "severity": "warn"},
            {"gate": "provides_fix_suggestions", "severity": "warn"},
        ],
        "opinion_sources": [],
    }


def _build_research() -> dict:
    """研究/分析的预期结果标准。"""
    return {
        "task_type": "research",
        "required": [
            "output_parsable",
            "covers_main_question",
            "contains_actionable_insights",
        ],
        "forbidden": [
            "pure_summary_without_analysis",
            "unsupported_claims",
        ],
        "quality_gates": [
            {"gate": "cites_sources", "severity": "require"},
            {"gate": "identifies_gaps", "severity": "warn"},
            {"gate": "has_concrete_next_steps", "severity": "warn"},
        ],
        "opinion_sources": [],
    }


def _build_tool_call() -> dict:
    """工具调用的预期结果标准。"""
    return {
        "task_type": "tool_call",
        "required": [
            "tool_exists",
            "params_complete",
            "output_parsable",
        ],
        "forbidden": [
            "destructive_without_approval",
            "infinite_retry_loop",
        ],
        "quality_gates": [
            {"gate": "has_timeout", "severity": "require"},
            {"gate": "has_error_recovery", "severity": "warn"},
            {"gate": "logs_side_effects", "severity": "warn"},
        ],
        "opinion_sources": [],
    }


def _build_documentation() -> dict:
    """文档写作的预期结果标准。"""
    return {
        "task_type": "documentation",
        "required": [
            "output_parsable",
            "covers_main_topic",
            "logical_structure",
        ],
        "forbidden": [
            "empty_sections",
            "contradictory_statements",
        ],
        "quality_gates": [
            {"gate": "has_toc_or_overview", "severity": "warn"},
            {"gate": "has_code_examples_when_relevant", "severity": "warn"},
            {"gate": "target_audience_appropriate", "severity": "require"},
        ],
        "opinion_sources": [],
    }


def _build_architecture_design() -> dict:
    """架构设计的预期结果标准。"""
    return {
        "task_type": "architecture_design",
        "required": [
            "output_parsable",
            "system_boundaries_defined",
            "component_interfaces_defined",
        ],
        "forbidden": [
            "magical_components",
            "missing_tradeoff_analysis",
        ],
        "quality_gates": [
            {"gate": "has_rationale", "severity": "require"},
            {"gate": "has_alternative_considered", "severity": "warn"},
            {"gate": "fault_tolerance_considered", "severity": "require"},
        ],
        "opinion_sources": [],
    }


def _build_planning() -> dict:
    """规划的预期结果标准。"""
    return {
        "task_type": "planning",
        "required": [
            "output_parsable",
            "tasks_decomposed",
            "dependencies_tracked",
        ],
        "forbidden": [
            "missing_verification_step",
            "infinite_decomposition",
        ],
        "quality_gates": [
            {"gate": "has_prio_labels", "severity": "require"},
            {"gate": "has_estimated_effort", "severity": "warn"},
            {"gate": "rollback_path_defined", "severity": "warn"},
        ],
        "opinion_sources": [],
    }


def _build_debugging() -> dict:
    """调试的预期结果标准。"""
    return {
        "task_type": "debugging",
        "required": [
            "output_parsable",
            "root_cause_identified",
            "reproducible",
        ],
        "forbidden": [
            "guess_without_evidence",
            "surface_fix_only",
        ],
        "quality_gates": [
            {"gate": "has_reproduction_steps", "severity": "require"},
            {"gate": "fix_validated", "severity": "require"},
            {"gate": "sibling_check_done", "severity": "warn"},
        ],
        "opinion_sources": [],
    }


# ── Schema 注册表 ──
_SCHEMA_BUILDERS = {
    "code_generation": _build_code_generation,
    "code_review": _build_code_review,
    "research": _build_research,
    "tool_call": _build_tool_call,
    "documentation": _build_documentation,
    "architecture_design": _build_architecture_design,
    "planning": _build_planning,
    "debugging": _build_debugging,
}


# ════════════════════════════════════════════════════════
# 公共接口
# ════════════════════════════════════════════════════════

def expected_result_schema(task_type: str) -> dict:
    """获取指定 task_type 的预期结果 Schema。

    IO-S 的 verify 钩子调用此接口获取验证标准。
    IO-S 只需要 `required` 和 `forbidden` 两个字段。
    `quality_gates` 是可选的辅助信息。

    Args:
        task_type: 任务类型，来自 TASK_TYPES 枚举。

    Returns:
        Schema dict 包含 required/forbidden/quality_gates/opinion_sources。
        如果 task_type 未知，返回通用 schema。
    """
    builder = _SCHEMA_BUILDERS.get(task_type)
    if builder:
        return builder()

    # 未知 task_type → 返回通用 schema（后续从 opinion 学习）
    logger.warning(f"未知 task_type: {task_type}，返回通用 schema")
    return {
        "task_type": task_type,
        "required": [
            "output_parsable",
            "covers_main_objective",
        ],
        "forbidden": [
            "unhandled_errors",
        ],
        "quality_gates": [
            {"gate": "has_verification", "severity": "warn"},
        ],
        "opinion_sources": [],
    }


def list_task_types() -> list[str]:
    """返回所有已注册的 task_type 列表。"""
    return list(TASK_TYPES)


def register_task_type(task_type: str, builder_fn) -> None:
    """动态注册新的 task_type（从 opinion 学习时使用）。

    Args:
        task_type: 新 task_type 名称。
        builder_fn: 返回 schema dict 的工厂函数。
    """
    if task_type not in TASK_TYPES:
        TASK_TYPES.append(task_type)
    _SCHEMA_BUILDERS[task_type] = builder_fn
    logger.info(f"已注册 task_type: {task_type}")


def add_opinion_source(task_type: str, opinion_id: str) -> bool:
    """将 opinion 关联到指定 task_type 的 schema。

    当 belief_update 从 IO-S verify 结果中学习到新 opinion 时调用。
    这允许 schema 随着认知 evolution。

    Args:
        task_type: 要关联的 task_type。
        opinion_id: opinion 标识符。

    Returns:
        True 如果关联成功，False 如果 task_type 未知。
    """
    schema = expected_result_schema(task_type)
    if "opinion_sources" not in schema:
        return False
    if opinion_id not in schema["opinion_sources"]:
        schema["opinion_sources"].append(opinion_id)
    return True


def schema_matches(task_type: str, result: dict) -> dict:
    """检查结果是否符合 task_type 的 Schema。

    这是 ISA 提供给 IO-S 的验证辅助函数。
    IO-S 可以在 verify 钩子中调用此函数快速判断。

    Args:
        task_type: 要验证的 task_type。
        result: 实际执行结果 {output, ...}。

    Returns:
        {passed: bool, failures: [str], warnings: [str]}。
    """
    schema = expected_result_schema(task_type)
    failures = []
    warnings = []

    # 检查 required
    required_checks = {
        "output_parsable": "output" in result and result["output"] is not None,
        "no_syntax_error": result.get("syntax_valid", True),
        "covers_main_logic": result.get("logic_coverage", 0) > 0,
        "covers_main_question": result.get("question_coverage", False),
        "covers_main_topic": result.get("topic_coverage", False),
        "tool_exists": result.get("tool_found", True),
        "params_complete": result.get("params_valid", False),
        # ... 更多检查点随 schema 扩展自动更新
    }

    for req in schema.get("required", []):
        check = required_checks.get(req)
        if check is False:
            failures.append(f"required:{req}")

    # 检查 forbidden
    result_text = json.dumps(result, ensure_ascii=False)
    forbidden_patterns = {
        "hardcoded_secrets": any(kw in result_text for kw in ["password=", "api_key=", "secret="]),
        "shell_injection_patterns": "$(" in result_text or "`" in result_text,
        "unbounded_recursion": "while True" in result_text or "recursive" in result_text,
        "vague_approval_without_evidence": "looks good" in result_text or "seems fine" in result_text,
        "ignored_security_concerns": "security" not in result_text and "safe" not in result_text,
        "pure_summary_without_analysis": result.get("is_pure_summary", False),
    }

    for forbid in schema.get("forbidden", []):
        check = forbidden_patterns.get(forbid)
        if check is True:
            failures.append(f"forbidden:{forbid}")

    # 检查 quality_gates
    for gate in schema.get("quality_gates", []):
        gate_name = gate["gate"]
        severity = gate["severity"]
        # 简单启发式检查
        gate_checks = {
            "has_test": "test" in result_text or "unittest" in result_text,
            "has_error_handling": "try" in result_text or "except" in result_text or "error" in result_text,
            "docstring_present": result.get("has_docstring", False),
            "has_line_specific_comments": result.get("has_inline_comments", False),
            "cites_sources": "source" in result_text or "reference" in result_text or "arxiv" in result_text,
            "has_timeout": "timeout" in result_text,
        }
        check = gate_checks.get(gate_name)
        if check is False and severity == "require":
            failures.append(f"required_gate:{gate_name}")
        elif check is False and severity == "warn":
            warnings.append(f"warn_gate:{gate_name}")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
    }


# ════════════════════════════════════════════════════════
# 诊断
# ════════════════════════════════════════════════════════

def health() -> dict:
    """诊断意见管理器健康状态。"""
    return {
        "module": "opinion_manager",
        "version": OPINION_SCHEMA_VERSION,
        "registered_types": len(TASK_TYPES),
        "task_types": list(TASK_TYPES),
        "schema_count": len(_SCHEMA_BUILDERS),
        "has_fallback": True,
    }


if __name__ == "__main__":
    # CLI 自检
    print(f"opinion_manager v{OPINION_SCHEMA_VERSION}")
    print(f"注册 task_types: {len(TASK_TYPES)}")
    for tt in TASK_TYPES:
        s = expected_result_schema(tt)
        req_count = len(s["required"])
        forbid_count = len(s["forbidden"])
        gate_count = len(s["quality_gates"])
        print(f"  {tt:>25s} | required={req_count} forbidden={forbid_count} gates={gate_count}")
    print(f"\n健康: {json.dumps(health(), indent=2, ensure_ascii=False)}")
