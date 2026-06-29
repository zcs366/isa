#!/usr/bin/env python3
"""
ISA belief_update.py — 信念更新模块 v0.2
=========================================

v0.1: stub骨架（记录到JSONL，不更新opinion）
v0.2: 完整实现（RECALL审计 + opinion置信度更新 + 矛盾检测）

接口：
  on_verify_result(tool_name, params, result, verdict, task_type) -> dict
    - IO-S verify钩子在每轮工具调用后回调
    - verdict: "pass" | "fail" | "warn"
    - 返回: {opinion_updated, confidence_delta, new_opinion_created, contradictions_detected}

设计原则：
  置信度更新策略：增量（每次±δ），非批量。
  pass → confidence + 0.05
  fail → confidence - 0.10（双重惩罚）
  warn → 不变
  支持 opinion 矛盾检测（future extension）
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("isa.belief_update")

BELIEF_UPDATE_VERSION = "0.2.0"

CONFIDENCE_DELTA_PASS = 0.05
CONFIDENCE_DELTA_FAIL = -0.10
OPINION_MIN_CONFIDENCE = 0.0
OPINION_MAX_CONFIDENCE = 1.0


# ════════════════════════════════════════════════════
# Opinion 存储
# ════════════════════════════════════════════════════

_OPINIONS_PATH = None
_verify_records_path = None


def _opinions_path() -> str:
    global _OPINIONS_PATH
    if _OPINIONS_PATH is None:
        _OPINIONS_PATH = str(Path.home() / ".hermes" / "isa" / "opinions.jsonl")
    return _OPINIONS_PATH


def _records_path() -> str:
    global _verify_records_path
    if _verify_records_path is None:
        _verify_records_path = str(Path.home() / ".hermes" / "isa" / "verify_records.jsonl")
    return _verify_records_path


def _load_opinions() -> list:
    path = Path(_opinions_path())
    if not path.exists():
        return []
    opinions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    opinions.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return opinions


def _save_opinion(opinion: dict) -> None:
    path = Path(_opinions_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(opinion, ensure_ascii=False) + "\n")


def _find_matching_opinions(opinions: list, tool_name: str, task_type: Optional[str]) -> list:
    """通过关键词匹配找到相关的opinion。"""
    matches = []
    tool_lower = tool_name.lower()
    task_lower = (task_type or "").lower()

    for op in opinions:
        text = op.get("text", "").lower()
        tags = [t.lower() for t in op.get("tags", [])]
        # 工具名匹配
        if tool_lower in text or tool_lower in tags:
            matches.append(op)
        # task_type匹配
        elif task_lower and task_lower in text:
            matches.append(op)
        # 关键词匹配（opinion中的keywords字段）
        elif any(kw.lower() in tool_lower for kw in op.get("keywords", [])):
            matches.append(op)

    return matches


def _update_opinion_confidence(opinion: dict, delta: float) -> dict:
    """更新opinion的置信度，边界裁剪。"""
    old_conf = opinion.get("confidence", 0.5)
    new_conf = max(OPINION_MIN_CONFIDENCE,
                   min(OPINION_MAX_CONFIDENCE, old_conf + delta))
    opinion["confidence"] = round(new_conf, 4)
    opinion["evidence_count"] = opinion.get("evidence_count", 0) + 1
    opinion["last_updated"] = datetime.now(timezone.utc).isoformat()
    return opinion


def _detect_contradictions(opinions: list, new_verdict: str, tool_name: str) -> list:
    """检测新verdict与已有opinion之间的矛盾。"""
    contradictions = []
    if new_verdict == "fail":
        for op in opinions:
            if op.get("confidence", 0) > 0.7 and tool_name.lower() in op.get("text", "").lower():
                contradictions.append({
                    "opinion_id": op.get("id", "unknown"),
                    "opinion_text": op.get("text", "")[:100],
                    "opinion_confidence": op.get("confidence", 0),
                    "reason": f"高置信度opinion({op.get('confidence', 0):.2f})但工具{tool_name}执行失败",
                })
    return contradictions


# ════════════════════════════════════════════════════
# 核心接口
# ════════════════════════════════════════════════════

def on_verify_result(
    tool_name: str,
    params: dict,
    result: dict,
    verdict: str,
    task_type: Optional[str] = None,
) -> dict:
    """接收 IO-S verify 结果，更新 opinion 置信度。

    完整实现：
    1. 加载现有opinions
    2. 匹配相关opinion（工具名/task_type/关键词）
    3. 根据verdict更新置信度（pass+0.05, fail-0.10）
    4. 检测矛盾
    5. 写RECALL审计轨迹
    6. 记录verify记录到JSONL
    """
    now = datetime.now(timezone.utc).isoformat()
    logger.info(f"on_verify_result: tool={tool_name} verdict={verdict} task={task_type}")

    # 1. 加载opinions
    opinions = _load_opinions()

    # 2. 匹配相关opinion
    matching = _find_matching_opinions(opinions, tool_name, task_type)

    # 3. 置信度更新
    delta = 0.0
    if verdict == "pass":
        delta = CONFIDENCE_DELTA_PASS
    elif verdict == "fail":
        delta = CONFIDENCE_DELTA_FAIL
    # warn: delta stays 0

    opinion_updated = False
    updated_opinions = []
    for op in matching:
        op = _update_opinion_confidence(op, delta)
        updated_opinions.append(op)
        opinion_updated = True

    # 4. 矛盾检测
    contradictions = _detect_contradictions(opinions, verdict, tool_name)

    # 5. 写verify记录
    record = {
        "ts": now,
        "tool_name": tool_name,
        "verdict": verdict,
        "task_type": task_type or "unknown",
        "confidence_delta": delta,
        "opinion_matches": len(matching),
        "contradictions": len(contradictions),
        "params_snapshot": {k: str(v)[:100] for k, v in params.items()},
    }
    _append_record(record)

    # 6. 写RECALL审计轨迹
    _append_recall(tool_name, verdict, delta, task_type, len(matching), len(contradictions))

    return {
        "opinion_updated": opinion_updated,
        "confidence_delta": delta,
        "new_opinion_created": False,
        "contradictions_detected": len(contradictions),
        "contradiction_details": contradictions,
        "opinions_matched": len(matching),
        "updated_opinions": updated_opinions,
        "record_id": now,
        "version": BELIEF_UPDATE_VERSION,
    }


# ════════════════════════════════════════════════════
# 存储
# ════════════════════════════════════════════════════

def _append_record(record: dict) -> None:
    path = Path(_records_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_recall(tool_name: str, verdict: str, delta: float,
                   task_type: Optional[str], matched: int, contradictions: int) -> None:
    """写RECALL审计轨迹（通过recall_append.py如果可用，否则直接追加）。"""
    recall_path = Path.home() / ".hermes" / "RECALL.jsonl"
    entry = {
        "type": "note",
        "ts": datetime.now(timezone.utc).isoformat(),
        "content": f"[ISA belief_update] verify结果: tool={tool_name} verdict={verdict} "
                   f"confidence_delta={delta:+.2f} task_type={task_type or 'unknown'} "
                   f"opinions_matched={matched} contradictions={contradictions}",
        "agent": "isa-belief-update",
        "written_by": "belief_update",
        "trust": 0.9,
    }
    try:
        recall_path.parent.mkdir(parents=True, exist_ok=True)
        with open(recall_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"RECALL写入跳过: {e}")


# ════════════════════════════════════════════════════
# 查询接口
# ════════════════════════════════════════════════════

def get_recent_verdicts(limit: int = 20) -> list:
    path = Path(_records_path())
    if not path.exists():
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records[-limit:]


def get_tool_stats(tool_name: str) -> dict:
    records = get_recent_verdicts(1000)
    tool_records = [r for r in records if r.get("tool_name") == tool_name]
    total = len(tool_records)
    if total == 0:
        return {"tool_name": tool_name, "total": 0, "pass_rate": 0.0}
    passes = sum(1 for r in tool_records if r.get("verdict") == "pass")
    return {
        "tool_name": tool_name,
        "total": total,
        "pass_rate": round(passes / total, 3) if total else 0.0,
        "pass_count": passes,
        "fail_count": total - passes,
        "last_verdict": tool_records[-1].get("verdict"),
        "avg_delta": round(sum(r.get("confidence_delta", 0) for r in tool_records) / total, 4),
    }


def get_opinions_summary() -> dict:
    opinions = _load_opinions()
    if not opinions:
        return {"total": 0, "avg_confidence": 0.0, "high_confidence": 0, "low_confidence": 0}
    confs = [o.get("confidence", 0.5) for o in opinions]
    return {
        "total": len(opinions),
        "avg_confidence": round(sum(confs) / len(confs), 3),
        "high_confidence": sum(1 for c in confs if c >= 0.7),
        "low_confidence": sum(1 for c in confs if c < 0.3),
    }


def health() -> dict:
    path = Path(_records_path())
    record_count = 0
    if path.exists():
        with open(path) as f:
            record_count = sum(1 for _ in f)
    return {
        "module": "belief_update",
        "version": BELIEF_UPDATE_VERSION,
        "status": "active",
        "record_count": record_count,
        "records_path": str(path),
        "opinions_path": str(_opinions_path()),
        "has_on_verify": True,
        "confidence_delta_pass": CONFIDENCE_DELTA_PASS,
        "confidence_delta_fail": CONFIDENCE_DELTA_FAIL,
    }


if __name__ == "__main__":
    print(f"belief_update v{BELIEF_UPDATE_VERSION}")
    print("=" * 50)

    # 测试1: pass verdict
    r1 = on_verify_result(
        tool_name="web_search",
        params={"query": "test"},
        result={"output": "test results"},
        verdict="pass",
        task_type="research",
    )
    print(f"\n✅ pass verdict: opinions_matched={r1['opinions_matched']} delta={r1['confidence_delta']:+.2f}")

    # 测试2: fail verdict
    r2 = on_verify_result(
        tool_name="shell",
        params={"command": "rm -rf /"},
        result={"error": "denied"},
        verdict="fail",
        task_type="tool_call",
    )
    print(f"❌ fail verdict: opinions_matched={r2['opinions_matched']} contradictions={r2['contradictions_detected']}")

    # 统计
    stats = get_tool_stats("web_search")
    print(f"\n📊 web_search统计: {json.dumps(stats, indent=2, ensure_ascii=False)}")

    # 健康
    h = health()
    print(f"\n🟢 健康: {json.dumps(h, indent=2, ensure_ascii=False)}")
