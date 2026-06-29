#!/usr/bin/env python3
"""
章鱼触须①：session_search（FTS5全文搜索）
数据源：Hermes session_search() 工具
流程：L0粗捞→L1洗矿
"""

import json
import sys
import os
from typing import Any


def _load_washing_prompt() -> str:
    """读取洗矿prompt模板"""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompts", "tentacle_washing.txt"
    )
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def phase0_gross_collect(query: str, limit: int = 10) -> dict:
    """L0粗捞：调用session_search获取匹配片段"""
    # 在独立子Agent中运行，session_search通过delegate_task上下文注入
    # 这里定义数据收集逻辑，由octopus.py的delegate_task调用
    return {
        "source": "session",
        "query": query,
        "status": "pending",
        "raw": []
    }


def phase1_wash(raw_data: dict) -> dict:
    """L1洗矿：调用轻LLM抽取结构化事实"""
    # 洗矿本身也通过delegate_task委托给轻量子Agent
    # 此函数仅定义数据格式
    facts = []
    for item in raw_data.get("raw", []):
        facts.append(item)
    return {
        "source": "session",
        "query": raw_data.get("query", ""),
        "facts": facts
    }


def build_delegate_task(query: str, limit: int = 10) -> dict:
    """构建触须的delegate_task参数——由octopus主脑调用"""
    prompt_template = _load_washing_prompt()
    return {
        "goal": f"在session数据库中搜索'{query}'相关的内容，提取结构化事实",
        "context": f"""你是一条章鱼触须，负责从session_search中搜索信息。

步骤：
1. 调用 session_search(query="{query}", limit={limit}) 获取原始片段
2. 用以下prompt模板清洗数据：

{prompt_template}

替换模板中的变量：
- {{source_description}} → "Hermes会话数据库（FTS5全文搜索），包含用户与我之间的所有对话记录"
- {{query}} → "{query}"
- {{raw_snippets}} → 你刚获取的session_search结果

3. 只输出清洗后的JSON数组

注意：如果你的环境不支持直接调用session_search，以JSON格式输出原始数据占位符也可。"""
    }


if __name__ == "__main__":
    # 独立运行测试
    query = sys.argv[1] if len(sys.argv) > 1 else "联邦制"
    task = build_delegate_task(query)
    print(json.dumps(task, ensure_ascii=False, indent=2))
