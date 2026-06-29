#!/usr/bin/env python3
"""jiak_emergence.py — jiak涌现引擎 (M1)
调 vLLM (或退化到关键词匹配) 判断"两张卡是否讨论同一现象"。
将涌现结果写入 jiak cards 的 insights 字段。

用法:
  python3 jiak_emergence.py                           # 全量扫描
  python3 jiak_emergence.py --pair card_a card_b     # 指定两张
  python3 jiak_emergence.py --no-llm                 # 纯关键词模式
"""
import json, os, sys, requests
from pathlib import Path

JIAK_DIR = Path.home() / ".hermes" / "jiak"
CARDS_DIR = JIAK_DIR / "cards"
VLLM_URL = "http://localhost:8000/v1/chat/completions"
EMERGENCE_NOTE = CARDS_DIR.parent / "emergence_notes.jsonl"


def read_all_cards() -> dict[str, dict]:
    """读取所有卡片"""
    cards = {}
    for f in sorted(CARDS_DIR.glob("*.json")):
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
            cards[f.stem] = card
        except Exception:
            continue
    return cards


def call_vllm(prompt: str) -> str:
    """调 vLLM 判断两个卡片是否讨论同一现象"""
    try:
        resp = requests.post(VLLM_URL, json={
            "model": "Qwen3.5-9B",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 50,
            "temperature": 0.1,
        }, timeout=30)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return ""


def keyword_emergence(card_a: dict, card_b: dict) -> tuple[float, str]:
    """纯关键词模式检测涌现"""
    text_a = (card_a.get("summary", "") + " " + " ".join(card_a.get("keywords", []))).lower()
    text_b = (card_b.get("summary", "") + " " + " ".join(card_b.get("keywords", []))).lower()

    # 共享关键词
    kw_a = set(k.lower() for k in card_a.get("keywords", []))
    kw_b = set(k.lower() for k in card_b.get("keywords", []))
    shared = kw_a & kw_b

    if not shared:
        return 0.0, ""

    # 计算得分
    score = len(shared) / max(len(kw_a | kw_b), 1)
    reason = f"共享关键词: {', '.join(list(shared)[:5])}"
    return round(score * 10, 1), reason


def detect_emergence_pairs(cards: dict, use_llm: bool = False) -> list[dict]:
    """检测所有卡片对中的涌现"""
    results = []
    ids = list(cards.keys())

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            id_a, id_b = ids[i], ids[j]
            card_a, card_b = cards[id_a], cards[id_b]

            # 跳过非active卡
            if card_a.get("status") != "active" or card_b.get("status") != "active":
                continue

            score, reason = keyword_emergence(card_a, card_b)

            if use_llm and score > 0:
                prompt = (
                    f"卡A: {card_a.get('title')}\n{card_a.get('summary', '')[:200]}\n\n"
                    f"卡B: {card_b.get('title')}\n{card_b.get('summary', '')[:200]}\n\n"
                    f"它们讨论的是同一现象吗？只回答'是'或'否'。"
                )
                llm_verdict = call_vllm(prompt)
                if llm_verdict and "是" in llm_verdict:
                    score += 5  # LLM 确认加分
                    reason += "; LLM确认"
                elif llm_verdict and "否" in llm_verdict:
                    score = 0  # LLM 否定

            if score >= 1.0:
                results.append({
                    "card_a": id_a,
                    "card_b": id_b,
                    "emergence_score": score,
                    "reason": reason,
                })

    results.sort(key=lambda x: x["emergence_score"], reverse=True)
    return results


def write_emergence(result: dict):
    """将涌现结果写入 emergence_notes.jsonl"""
    entry = {
        "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "source": "jiak_emergence",
        "card_a": result["card_a"],
        "card_b": result["card_b"],
        "score": result["emergence_score"],
        "reason": result["reason"],
    }
    with open(EMERGENCE_NOTE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  📝 涌现: {result['card_a']} ↔ {result['card_b']} (score={result['emergence_score']})")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="jiak涌现引擎")
    parser.add_argument("--pair", nargs=2, metavar=("card_a", "card_b"), help="指定两张卡片")
    parser.add_argument("--no-llm", action="store_true", help="纯关键词模式")
    args = parser.parse_args()

    cards = read_all_cards()
    print(f"📚 加载 {len(cards)} 张卡片")

    if args.pair:
        id_a, id_b = args.pair
        if id_a not in cards or id_b not in cards:
            print(f"❌ 卡片不存在")
            return
        score, reason = keyword_emergence(cards[id_a], cards[id_b])
        print(f"\n{id_a} ↔ {id_b}")
        print(f"  涌现得分: {score}")
        print(f"  原因: {reason}")
        if score >= 1.0:
            write_emergence({"card_a": id_a, "card_b": id_b, "emergence_score": score, "reason": reason})
        return

    results = detect_emergence_pairs(cards, use_llm=not args.no_llm)

    print(f"\n🔍 检测到 {len(results)} 对涌现:")
    for r in results[:10]:
        print(f"  {r['card_a']:<35s} ↔ {r['card_b']:<35s} score={r['emergence_score']}")
        print(f"    {r['reason']}")
        write_emergence(r)

    print(f"\n💾 已写入 {len(results)} 条涌现到 {EMERGENCE_NOTE}")


if __name__ == "__main__":
    main()
