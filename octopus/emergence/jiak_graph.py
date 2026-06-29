#!/usr/bin/env python3
"""jiak_graph.py — jiak知识图谱构建器 (M1)
遍历 cards/*.json，用 embedding 聚类，输出跨卡关联JSON。

用法:
  python3 jiak_graph.py                          # → 标准输出
  python3 jiak_graph.py --save                   # → 写入 cards/cross_card_graph.json
  python3 jiak_graph.py --cluster-only           # 只做聚类（无embedding，更快）
"""
import json, os, sys
from pathlib import Path
from collections import defaultdict
import jieba

JIAK_DIR = Path.home() / ".hermes" / "jiak"
CARDS_DIR = JIAK_DIR / "cards"
GRAPH_PATH = CARDS_DIR / "cross_card_graph.json"

# ─── 卡片特征提取 ─────────────────────────────────────

def extract_card_features(card: dict) -> dict:
    """从卡片中提取特征文本（用于embedding/聚类）"""
    parts = []
    parts.append(card.get("title", ""))
    parts.append(card.get("summary", ""))
    parts.append(" ".join(card.get("keywords", [])))
    for n in card.get("notes", []):
        if isinstance(n, dict):
            parts.append(n.get("content", ""))
    for d in card.get("decisions", []):
        if isinstance(d, dict):
            parts.append(d.get("content", ""))
    return {
        "title": card.get("title", ""),
        "text": "\n".join(parts),
        "keywords": card.get("keywords", []),
        "status": card.get("status", "active"),
    }


def keyword_overlap(kw1: list, kw2: list) -> float:
    """关键词重叠度 — jieba分词后Jaccard相似度"""
    if not kw1 or not kw2:
        return 0.0
    # jieba分词每个关键词，展开为子词集合
    s1 = set()
    for k in kw1:
        s1.update(jieba.cut(k.lower()))
    s2 = set()
    for k in kw2:
        s2.update(jieba.cut(k.lower()))
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


# ─── 构建关联图 ───────────────────────────────────────

def build_graph() -> dict:
    """构建跨卡关联图"""
    cards = {}
    for f in sorted(CARDS_DIR.glob("*.json")):
        card_id = f.stem
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
            cards[card_id] = extract_card_features(card)
        except Exception as e:
            print(f"  ⚠️ 跳过 {card_id}: {e}", file=sys.stderr)

    print(f"📊 加载 {len(cards)} 张卡片")

    # 计算两两关联
    edges = []
    for i, (id1, c1) in enumerate(cards.items()):
        for id2, c2 in list(cards.items())[i + 1:]:
            score = 0.0
            reasons = []

            # 维度1: 关键词重叠
            kw_score = keyword_overlap(c1["keywords"], c2["keywords"])
            if kw_score > 0:
                score += kw_score * 3
                reasons.append(f"关键词重叠({kw_score:.2f})")

            # 维度2: 文本中共享词汇（简单token匹配）
            tokens1 = set(c1["text"])
            tokens2 = set(c2["text"])
            shared = tokens1 & tokens2
            if shared:
                # 取有意义的共享词
                meaningful = {t for t in shared if len(t) >= 2}
                if meaningful:
                    overlap_ratio = len(meaningful) / max(len(tokens1), len(tokens2))
                    if overlap_ratio > 0.01:
                        score += overlap_ratio * 2
                        reasons.append(f"文本词汇重叠({overlap_ratio:.2f})")

            # 维度3: title 共享词
            title_tokens1 = set(c1["title"])
            title_tokens2 = set(c2["title"])
            shared_title = {t for t in (title_tokens1 & title_tokens2) if len(t) >= 2}
            if shared_title:
                score += 0.5 * len(shared_title)
                reasons.append(f"标题共享词({','.join(list(shared_title)[:3])})")

            if score >= 0.5:
                edges.append({
                    "source": id1,
                    "target": id2,
                    "score": round(score, 2),
                    "reasons": reasons,
                })

    edges.sort(key=lambda x: x["score"], reverse=True)

    # 统计每个节点的度
    degree = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    # 社区检测：简单连通分量
    visited = set()
    communities = []
    nodes = list(cards.keys())
    # 构建邻接表（只保留强关联 score>=2.0）
    adj = defaultdict(set)
    for e in edges:
        if e["score"] >= 2.0:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])

    for n in nodes:
        if n in visited:
            continue
        # BFS
        queue = [n]
        community = []
        while queue:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            community.append(cur)
            for neighbor in adj.get(cur, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(community) >= 2:
            communities.append(sorted(community))

    graph = {
        "total_cards": len(cards),
        "total_edges": len(edges),
        "strong_edges": len([e for e in edges if e["score"] >= 2.0]),
        "communities": len(communities),
        "top_edges": edges[:20],
        "degree_ranking": sorted(degree.items(), key=lambda x: -x[1])[:15],
        "communities_detail": communities,
    }

    return graph


def save_graph(graph: dict):
    """保存关联图到文件"""
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 已保存: {GRAPH_PATH}")


def print_graph(graph: dict):
    """打印关联图摘要"""
    print(f"\n{'='*50}")
    print(f"📊 jiak知识图谱")
    print(f"{'='*50}")
    print(f"  卡片: {graph['total_cards']}")
    print(f"  关联边: {graph['total_edges']} (强关联: {graph['strong_edges']})")
    print(f"  社区: {graph['communities']}")
    print()
    print(f"  度数排名:")
    for card_id, deg in graph["degree_ranking"][:10]:
        print(f"    {card_id:<40s} {deg}条关联")
    print()
    print(f"  最强关联:")
    for e in graph["top_edges"][:5]:
        print(f"    {e['source']:<30s} ↔ {e['target']:<30s} score={e['score']}")
        print(f"      {', '.join(e['reasons'][:2])}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="jiak知识图谱构建器")
    parser.add_argument("--save", action="store_true", help="写入 cross_card_graph.json")
    parser.add_argument("--cluster-only", action="store_true", help="跳过embedding")
    args = parser.parse_args()

    graph = build_graph()
    print_graph(graph)

    if args.save:
        save_graph(graph)


if __name__ == "__main__":
    main()
