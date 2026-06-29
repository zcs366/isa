#!/usr/bin/env python3
"""recursive_loop.py — 递归回流桥 (M1)
jiak涌现结果 → 写入Δ胶囊dreaming input。
"""
import json, os, sys
from pathlib import Path

JIAK_DIR = Path.home() / ".hermes" / "jiak"
CAPSULE_INPUT = Path.home() / ".hermes" / "semantic_field" / "dreaming_input.json"
EMERGENCE_NOTES = JIAK_DIR / "emergence_notes.jsonl"


def read_emergence_notes(last_n: int = 20) -> list[dict]:
    """读取最近的涌现记录"""
    if not EMERGENCE_NOTES.exists():
        return []
    lines = EMERGENCE_NOTES.read_text(encoding="utf-8").strip().split("\n")
    results = []
    for line in lines[-last_n:]:
        try:
            results.append(json.loads(line))
        except Exception:
            continue
    return results


def format_dreaming_input(notes: list[dict]) -> list[dict]:
    """将涌现记录格式化为Δ胶囊的dreaming input"""
    dreams = []
    for n in notes:
        dream = {
            "source": "jiak_emergence",
            "type": "cross_card_emergence",
            "pair": [n.get("card_a", ""), n.get("card_b", "")],
            "score": n.get("score", 0),
            "reason": n.get("reason", ""),
            "timestamp": n.get("ts", ""),
        }
        dreams.append(dream)
    return dreams


def push_to_capsule(dreams: list[dict]):
    """写入Δ胶囊dreaming input"""
    CAPSULE_INPUT.parent.mkdir(parents=True, exist_ok=True)
    # 合并现有内容
    existing = []
    if CAPSULE_INPUT.exists():
        try:
            existing = json.loads(CAPSULE_INPUT.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            pass

    # 追加新dreams
    existing.extend(dreams)

    # 限制总量
    if len(existing) > 100:
        existing = existing[-100:]

    CAPSULE_INPUT.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    print("🔄 递归回流桥")
    print("=" * 40)

    notes = read_emergence_notes()
    if not notes:
        print("⚠️ 无涌现记录")
        return

    dreams = format_dreaming_input(notes)
    push_to_capsule(dreams)

    print(f"  ✨ {len(dreams)} 条涌现 → Δ胶囊 dreaming_input")
    print(f"  📍 {CAPSULE_INPUT}")
    for d in dreams[:5]:
        print(f"    {d['pair'][0]} ↔ {d['pair'][1]} (score={d['score']})")


if __name__ == "__main__":
    main()
