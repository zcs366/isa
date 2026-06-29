#!/usr/bin/env python3
"""
章鱼触须②：jiak卡片（JSON结构化数据）
数据源：~/.hermes/jiak/cards/*.json + index.json
流程：L0粗捞→L1洗矿
"""

import json
import sys
import os
import glob


JIAK_HOME = os.path.expanduser("~/.hermes/jiak")


def _load_washing_prompt() -> str:
    """读取洗矿prompt模板"""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompts", "tentacle_washing.txt"
    )
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def phase0_gross_collect(query: str, max_cards: int = 5) -> dict:
    """
    L0粗捞：读index.json → 按关键词匹配 → 读命中卡片的summary+最新notes+decisions
    此函数可在主进程直接运行，也可通过delegate_task委托
    """
    index_path = os.path.join(JIAK_HOME, "index.json")
    if not os.path.exists(index_path):
        return {"source": "jiak", "query": query, "status": "error", "error": "index.json not found", "cards": [], "raw_snippets": []}

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    # 关键词匹配
    query_lower = query.lower()
    query_terms = set(query_lower.split())
    matched_cards = []

    for card_id, card_info in index.get("cards", {}).items():
        keywords = [k.lower() for k in card_info.get("keywords", [])]
        summary = (card_info.get("summary", "") or "").lower()
        title = (card_info.get("title", "") or "").lower()

        # 匹配得分：关键词匹配+标题匹配+摘要匹配
        score = 0
        for term in query_terms:
            if any(term in kw for kw in keywords):
                score += 3
            if term in title:
                score += 2
            if term in summary:
                score += 1

        if score > 0:
            matched_cards.append({
                "card_id": card_id,
                "title": card_info.get("title", ""),
                "summary": card_info.get("summary", ""),
                "keywords": card_info.get("keywords", []),
                "status": card_info.get("status", ""),
                "updated": card_info.get("updated", ""),
                "score": score
            })

    # 按匹配度排序
    matched_cards.sort(key=lambda x: x["score"], reverse=True)
    matched_cards = matched_cards[:max_cards]

    # 读取命中卡片的详细内容
    raw_snippets = []
    cards_detail = []
    for card in matched_cards:
        card_path = os.path.join(JIAK_HOME, "cards", f"{card['card_id']}.json")
        if not os.path.exists(card_path):
            continue
        try:
            with open(card_path, "r", encoding="utf-8") as f:
                card_data = json.load(f)

            # 提取summary + 最新5条notes + decisions
            notes = card_data.get("notes", [])[-5:]
            decisions = card_data.get("decisions", [])[-3:]

            card_detail = {
                "card_id": card["card_id"],
                "title": card["title"],
                "summary": card_data.get("summary", ""),
                "recent_notes": notes,
                "recent_decisions": decisions,
                "status": card_data.get("status", ""),
                "updated": card_data.get("updated", "")
            }
            cards_detail.append(card_detail)

            # 构建原始片段
            snippet = f"[卡片:{card['card_id']}] {card['title']}\n摘要: {card_data.get('summary', '')}\n"
            for note in notes:
                snippet += f"笔记({note.get('ts','')}): {note.get('content','')[:200]}\n"
            for dec in decisions:
                snippet += f"决策({dec.get('date','')}): {dec.get('content','')[:200]}\n"
            raw_snippets.append(snippet)

        except (json.JSONDecodeError, KeyError) as e:
            raw_snippets.append(f"[卡片:{card['card_id']}] 读取失败: {e}")

    return {
        "source": "jiak",
        "query": query,
        "status": "ok",
        "cards": cards_detail,
        "raw_snippets": raw_snippets
    }


def build_delegate_task(query: str, max_cards: int = 5) -> dict:
    """构建触须的delegate_task参数——由octopus主脑调用"""
    prompt_template = _load_washing_prompt()
    return {
        "goal": f"在jiak知识卡片中搜索'{query}'相关的内容，提取结构化事实",
        "context": f"""你是一条章鱼触须，负责从jiak知识卡片中搜索信息。

步骤：
1. 读取 ~/.hermes/jiak/index.json，按关键词匹配与"{query}"相关的卡片
2. 读取匹配卡片的完整内容（summary + 最新notes + decisions）
3. 用以下prompt模板清洗数据：

{prompt_template}

替换模板中的变量：
- {{source_description}} → "jiak知识卡片系统——JSON结构化数据，包含研究洞察、决策记录、实验笔记"
- {{query}} → "{query}"
- {{raw_snippets}} → 你刚提取的jiak卡片内容

4. 只输出清洗后的JSON数组

注意：如果无法直接读取文件系统，输出包含原始卡片摘要的占位符JSON也可。"""
    }


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "联邦制"
    result = phase0_gross_collect(query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
