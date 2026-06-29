#!/usr/bin/env python3
"""
章鱼触须③：RECALL时间线（JSONL事件流）
数据源：~/.hermes/jiak/RECALL.jsonl
流程：L0粗捞→L1洗矿
"""

import json
import sys
import os
from datetime import datetime, timedelta


JIAK_HOME = os.path.expanduser("~/.hermes/jiak")
RECALL_PATH = os.path.join(JIAK_HOME, "RECALL.jsonl")


def _load_washing_prompt() -> str:
    """读取洗矿prompt模板"""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompts", "tentacle_washing.txt"
    )
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def phase0_gross_collect(query: str, tail_lines: int = 200) -> dict:
    """
    L0粗捞：读取RECALL.jsonl最后N行 → 按时间窗口+关键词过滤 → 提取相关事件
    此函数可在主进程直接运行，也可通过delegate_task委托
    """
    if not os.path.exists(RECALL_PATH):
        return {"source": "recall", "query": query, "status": "error", "error": "RECALL.jsonl not found", "events": [], "raw_snippets": []}

    # 读取最后N行
    lines = []
    try:
        with open(RECALL_PATH, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            lines = all_lines[-tail_lines:]
    except Exception as e:
        return {"source": "recall", "query": query, "status": "error", "error": str(e), "events": [], "raw_snippets": []}

    # 解析JSONL，按关键词过滤
    query_lower = query.lower()
    query_terms = set(query_lower.split())
    raw_events = []
    raw_snippets = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            # 关键词匹配
            event_str = json.dumps(event, ensure_ascii=False).lower()
            score = sum(1 for term in query_terms if term in event_str)
            if score > 0:
                raw_events.append(event)
                snippet = f"[{event.get('ts', event.get('timestamp', 'unknown'))}] "
                snippet += f"type={event.get('type', '?')} "
                snippet += f"agent={event.get('agent', '?')} "
                content = event.get('content', event.get('summary_short', event.get('result', '')))
                if isinstance(content, str):
                    snippet += content[:300]
                elif isinstance(content, dict):
                    snippet += json.dumps(content, ensure_ascii=False)[:200]
                raw_snippets.append(snippet)
        except json.JSONDecodeError:
            continue

    return {
        "source": "recall",
        "query": query,
        "status": "ok",
        "events": raw_events,
        "raw_snippets": raw_snippets
    }


def build_delegate_task(query: str, tail_lines: int = 200) -> dict:
    """构建触须的delegate_task参数——由octopus主脑调用"""
    prompt_template = _load_washing_prompt()
    return {
        "goal": f"在RECALL事件流中搜索'{query}'相关的事件，提取结构化事实",
        "context": f"""你是一条章鱼触须，负责从RECALL.jsonl事件流中搜索信息。

步骤：
1. 读取 ~/.hermes/jiak/RECALL.jsonl 的最后{tail_lines}行
2. 按关键词过滤与"{query}"相关的事件
3. 用以下prompt模板清洗数据：

{prompt_template}

替换模板中的变量：
- {{source_description}} → "RECALL.jsonl事件流——包含所有Agent的审计记录、决策、研究进展、jiak笔记的时间线"
- {{query}} → "{query}"
- {{raw_snippets}} → 你刚提取的RECALL事件片段

4. 只输出清洗后的JSON数组

注意：如果无法直接读取文件系统，输出占位符JSON也可。"""
    }


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "联邦制"
    result = phase0_gross_collect(query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
