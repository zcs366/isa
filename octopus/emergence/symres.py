#!/usr/bin/env python3
"""symres.py — Δ胶囊侧共鸣共振 (M1)
基于 IAH D₀ 谱系做跨 SA 模式匹配。

检测不同 session 中是否出现相似的主题模式（关键词共现+时间聚集），
输出共鸣事件。

用法:
  python3 symres.py                         # 全量扫描
  python3 symres.py --recent 50            # 只扫最近N条RECALL
"""
import json, os, sys, re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

JIAK_DIR = Path.home() / ".hermes" / "jiak"
RECALL_PATH = JIAK_DIR / "RECALL.jsonl"
SYMRES_OUT = JIAK_DIR.parent / "semantic_field" / "symres_events.json"


def load_records(last_n: int = 200) -> list[dict]:
    """读取 RECALL 记录"""
    if not RECALL_PATH.exists():
        return []
    lines = RECALL_PATH.read_text(encoding="utf-8").strip().split("\n")
    records = []
    for line in lines[-last_n:]:
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def extract_topic_signals(record: dict) -> list[str]:
    """从RECALL记录中提取主题信号（关键词）"""
    signals = set()

    for field in ("content", "summary", "summary_short", "subject", "body"):
        text = record.get(field, "")
        if not isinstance(text, str):
            continue
        # 提取中英文关键词（2字以上）
        for token in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', text):
            signals.add(token.lower()[:20])

    # cards字段也是信号
    for field in ("cards", "card_ids", "card"):
        cards = record.get(field, [])
        if isinstance(cards, str):
            signals.add(cards.lower()[:20])
        elif isinstance(cards, list):
            for c in cards:
                if isinstance(c, str):
                    signals.add(c.lower()[:20])

    return list(signals)


def detect_symmetry(records: list[dict], min_match: int = 3) -> list[dict]:
    """检测跨记录的主题共振"""
    # 按时间窗口分组（每5分钟一个窗口）
    windows = defaultdict(list)
    for rec in records:
        ts_str = rec.get("ts", "")
        if not ts_str:
            continue
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            window_key = dt.strftime("%Y-%m-%d %H:%M")  # 每分钟
            # 每5分钟
            minute_bucket = dt.minute // 5 * 5
            window_key = dt.strftime(f"%Y-%m-%d %H:{minute_bucket:02d}")
            windows[window_key].append(rec)
        except Exception:
            continue

    events = []
    seen_pairs = set()

    # 在相邻时间窗口内检测主题共现
    sorted_windows = sorted(windows.keys())

    for i, w_key in enumerate(sorted_windows):
        recs_i = windows[w_key]
        for rec_a in recs_i:
            signals_a = set(extract_topic_signals(rec_a))

            # 与后续窗口比较
            for j in range(i, min(i + 3, len(sorted_windows))):
                if j == i:
                    continue
                for rec_b in windows[sorted_windows[j]]:
                    signals_b = set(extract_topic_signals(rec_b))
                    common = signals_a & signals_b

                    if len(common) >= min_match:
                        pair_key = (rec_a.get("ts", ""), rec_b.get("ts", ""))
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        events.append({
                            "ts_a": rec_a.get("ts", ""),
                            "ts_b": rec_b.get("ts", ""),
                            "window_a": w_key,
                            "window_b": sorted_windows[j],
                            "common_signals": list(common)[:10],
                            "match_count": len(common),
                            "type_a": rec_a.get("type", ""),
                            "type_b": rec_b.get("type", ""),
                        })

    events.sort(key=lambda x: x["match_count"], reverse=True)
    return events


def save_events(events: list[dict]):
    """保存共鸣事件到文件"""
    SYMRES_OUT.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_events": len(events),
        "events": events[:30],
    }
    SYMRES_OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 已保存 {len(events)} 条共鸣事件")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Δ胶囊共鸣共振")
    parser.add_argument("--recent", type=int, default=200, help="扫描最近N条RECALL")
    parser.add_argument("--min-match", type=int, default=3, help="最小匹配信号数")
    args = parser.parse_args()

    print(f"🔍 共鸣共振扫描")
    print(f"  扫描: 最近{args.recent}条 RECALL")
    print(f"  最小匹配: {args.min_match}个信号")
    print("=" * 40)

    records = load_records(args.recent)
    print(f"  记录: {len(records)} 条")

    events = detect_symmetry(records, min_match=args.min_match)
    print(f"  共鸣事件: {len(events)} 条")

    if events:
        print(f"\n  最强共鸣:")
        for e in events[:5]:
            print(f"    {e['ts_a'][:19]} ↔ {e['ts_b'][:19]}")
            print(f"      信号: {', '.join(e['common_signals'][:5])}")
            print(f"      匹配: {e['match_count']}个")

    save_events(events)


if __name__ == "__main__":
    main()
