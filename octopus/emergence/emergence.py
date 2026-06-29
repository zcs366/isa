#!/usr/bin/env python3
"""emergence.py — Δ胶囊侧涌现引擎 (M1)
做梦时自动触发，检测跨卡涌现 → 写 jiak + RECALL。

用法:
  python3 emergence.py --once    # 单次运行
  python3 emergence.py --watch   # 持续监听（每60s检查）
"""
import json, os, sys, time
from pathlib import Path
from datetime import datetime, timezone

JIAK_DIR = Path.home() / ".hermes" / "jiak"
RECALL_PATH = JIAK_DIR / "RECALL.jsonl"
CARDS_DIR = JIAK_DIR / "cards"
DREAM_INPUT = Path.home() / ".hermes" / "semantic_field" / "dreaming_input.json"


def append_recall(entry: dict):
    """写入 RECALL"""
    with open(RECALL_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_dreaming_input() -> list[dict]:
    """检查 dream input 中的新涌现"""
    if not DREAM_INPUT.exists():
        return []
    try:
        data = json.loads(DREAM_INPUT.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        # 找未处理的新条目
        new = [d for d in data if d.get("source") == "jiak_emergence" and not d.get("processed")]
        return new
    except Exception:
        return []


def mark_processed(dreams: list[dict]):
    """标记已处理"""
    if not DREAM_INPUT.exists():
        return
    try:
        data = json.loads(DREAM_INPUT.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return
        # 标记匹配条目
        for d in data:
            for processed in dreams:
                # 处理两种格式
                p_a = processed.get("card_a", "")
                p_b = processed.get("card_b", "")
                pair_p = processed.get("pair", [])
                if not p_a and len(pair_p) >= 2:
                    p_a, p_b = pair_p[0], pair_p[1]
                d_a = d.get("card_a", "")
                d_b = d.get("card_b", "")
                pair_d = d.get("pair", [])
                if not d_a and len(pair_d) >= 2:
                    d_a, d_b = pair_d[0], pair_d[1]
                if (d_a == p_a and d_b == p_b) or (d_a == p_b and d_b == p_a):
                    d["processed"] = True
                    d["processed_at"] = datetime.now(timezone.utc).isoformat()
        DREAM_INPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def write_to_cards(emergence: dict):
    """将涌现写入卡片 insights"""
    card_id = emergence.get("card_a", "")
    if not card_id:
        return
    path = CARDS_DIR / f"{card_id}.json"
    if not path.exists():
        return
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
        if "insights" not in card:
            card["insights"] = []
        insight = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "emergence",
            "content": f"[涌现] 与 {emergence.get('card_b','?')} 关联: {emergence.get('reason','')} (score={emergence.get('score',0)})",
        }
        card["insights"].append(insight)
        card["updated"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def run_once():
    """单次运行"""
    print("🧠 Δ胶囊涌现引擎")
    print("=" * 40)

    # 1. 检查 dream input
    new_dreams = check_dreaming_input()
    print(f"  Dream input: {len(new_dreams)} 条新涌现")

    if not new_dreams:
        print("  ✅ 无新涌现")
        return

    # 2. 写入卡片和RECALL
    for dream in new_dreams:
        # 处理两种格式：直接card_a/card_b或pair数组
        card_a = dream.get("card_a", "")
        card_b = dream.get("card_b", "")
        if not card_a or not card_b:
            pair = dream.get("pair", [])
            if len(pair) >= 2:
                card_a, card_b = pair[0], pair[1]
        if not card_a or not card_b:
            continue

        write_to_cards({"card_a": card_a, "card_b": card_b,
                        "reason": dream.get("reason", ""),
                        "score": dream.get("score", 0)})
        append_recall({
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "jiak_note",
            "agent": "emergence",
            "cards": [card_a, card_b],
            "content": f"[涌现] {card_a} ↔ {card_b}: {dream.get('reason','')}",
            "summary_short": f"涌现: {card_a[:20]} ↔ {card_b[:20]}",
        })
        print(f"  📝 {card_a} ↔ {card_b}")

    # 3. 标记已处理
    mark_processed(new_dreams)
    print(f"\n  ✅ 已处理 {len(new_dreams)} 条涌现")


def watch_loop(interval: int = 60):
    """持续监听"""
    print(f"👁️ 持续监听 (每{interval}s)")
    try:
        while True:
            run_once()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  👋 停止")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Δ胶囊涌现引擎")
    parser.add_argument("--once", action="store_true", help="单次运行")
    parser.add_argument("--watch", action="store_true", help="持续监听")
    args = parser.parse_args()

    if args.watch:
        watch_loop()
    else:
        run_once()


if __name__ == "__main__":
    main()
