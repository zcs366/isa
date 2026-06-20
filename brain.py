#!/usr/bin/env python3
"""
ISA Brain v0.1 — jika内核的ISA集成层
=====================================

Brain是jika在ISA内部的化身。每个IsaAgent启动时初始化自己的Brain，
Brain管理该Agent的卡片目录、记忆检索和洞察写入。

架构位置：Core层内，与JSONL频道并列。
           Client ↔ Gateway ↔ Core(JSONL + Brain)

用法:
    brain = Brain("军师")
    brain.ingest_signal(sig)       # 信号进入→触发记忆检索
    cards = brain.recall("波扩散")  # 关键词检索
    brain.insight("新洞察内容")     # 写入洞察到相关卡片
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# jika内核路径——硬依赖
JIAK_API = Path.home() / ".hermes" / "jiak" / "jiak_api.py"
_JIAK_LOADED = False

def _ensure_jiak():
    """懒加载 jika API。避免循环导入。"""
    global _JIAK_LOADED
    if not _JIAK_LOADED:
        if str(JIAK_API.parent) not in sys.path:
            sys.path.insert(0, str(JIAK_API.parent))
        _JIAK_LOADED = True

# ═══════════════════════════════════════════════════════════
# Brain
# ═══════════════════════════════════════════════════════════

class Brain:
    """ISA Agent的jika大脑。

    每个Agent一个Brain实例。Brain管理该Agent的:
    - 卡片目录（cards/*.json）
    - 索引（index.json）
    - 时间线（RECALL.jsonl）
    """

    def __init__(self, agent_id: str, brain_dir: Path = None):
        self.agent_id = agent_id
        self.brain_dir = brain_dir or Path.home() / ".hermes" / "isa" / "brain" / agent_id
        self.brain_dir.mkdir(parents=True, exist_ok=True)

        self.cards_dir = self.brain_dir / "cards"
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.brain_dir / "index.json"
        self.recall_path = self.brain_dir / "RECALL.jsonl"

        # 初始化索引
        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({"cards": {}}, ensure_ascii=False, indent=2))

        self._session_insights: list[str] = []  # 本轮新洞察

        _ensure_jiak()
        from jiak_api import _read_json, _write_json, _append_jsonl
        self._read_json = _read_json
        self._write_json = _write_json
        self._append_jsonl = _append_jsonl

        print(f"[Brain] 🧠 {agent_id} 大脑初始化: {self.brain_dir}")

    # ── 卡片操作 ──

    def _read_card(self, card_id: str) -> dict:
        path = self.cards_dir / f"{card_id}.json"
        return self._read_json(path) if path.exists() else {}

    def _write_card(self, card_id: str, data: dict):
        data["updated"] = datetime.now(timezone.utc).isoformat()
        self._write_json(self.cards_dir / f"{card_id}.json", data)
        self._update_index(card_id, data)

    def _update_index(self, card_id: str, data: dict):
        index = self._read_json(self.index_path)
        index.setdefault("cards", {})[card_id] = {
            "title": data.get("title", card_id),
            "keywords": data.get("keywords", []),
            "summary": data.get("summary", ""),
            "status": data.get("status", "active"),
            "updated": data.get("updated", ""),
            "size": str(self.cards_dir / f"{card_id}.json"),
        }
        self._write_json(self.index_path, index)

    # ── 核心：信号摄入→记忆检索 ──

    def ingest_signal(self, signal: dict) -> list[dict]:
        """收到一条ISA信号后，触发记忆检索。

        返回匹配的卡片列表（摘要+相似度），供Agent上下文使用。
        """
        body = signal.get("body", "")
        source = signal.get("source", "?")
        sig_type = signal.get("type", "message")

        # 提取关键词
        keywords = self._extract_keywords(body)

        # 检索匹配卡片
        matched = self._search(keywords, limit=3)

        # 追加RECALL
        self._append_jsonl(self.recall_path, {
            "type": "signal",
            "source": source,
            "body": body[:200],
            "keywords": keywords,
            "matched_cards": [m["card_id"] for m in matched],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return matched

    def _extract_keywords(self, text: str) -> list[str]:
        """从文本中提取关键词（简单版——按空格/标点分词取长度>1的词）。"""
        import re
        words = re.findall(r'[\w\u4e00-\u9fff]{2,}', text)
        # 去重、去停用词
        stop = {'的','了','是','在','我','你','他','她','它','们','这','那','和','与','或','吗','呢','吧','啊','哦','嗯','呀','哈'}
        return list(dict.fromkeys([w for w in words if w not in stop]))[:10]

    def _search(self, keywords: list[str], limit: int = 3) -> list[dict]:
        """关键词匹配检索。简单版——按关键词命中数排序。"""
        index = self._read_json(self.index_path)
        cards = index.get("cards", {})

        scored = []
        for card_id, meta in cards.items():
            card_kw = meta.get("keywords", [])
            score = sum(1 for kw in keywords if any(kw in ck for ck in card_kw))
            if score > 0:
                scored.append((score, card_id, meta))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"card_id": cid, "score": s, "title": m.get("title",""),
                 "summary": m.get("summary","")} for s, cid, m in scored[:limit]]

    # ── 洞察写入 ──

    def insight(self, card_id: str, content: str):
        """将一个新洞察写入指定卡片。

        如果卡片不存在，自动创建。
        """
        card = self._read_card(card_id)
        if not card:
            card = {
                "card_id": card_id,
                "title": card_id,
                "status": "active",
                "created": datetime.now(timezone.utc).isoformat(),
                "keywords": [],
                "summary": "",
                "decisions": [],
                "notes": [],
            }

        card.setdefault("notes", []).append({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "content": content,
        })
        card["summary"] = content[:200]

        self._write_card(card_id, card)
        self._session_insights.append(f"[{card_id}] {content[:100]}")

        # 写入RECALL
        self._append_jsonl(self.recall_path, {
            "type": "insight",
            "card_id": card_id,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        print(f"[Brain] 💡 {self.agent_id} 新洞察 → {card_id}: {content[:60]}...")

    # ── 会话洞察汇总 ──

    @property
    def new_insights(self) -> list[str]:
        """本轮新产生的洞察列表。"""
        return list(self._session_insights)
