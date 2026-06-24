#!/usr/bin/env python3
"""
ISA Brain v0.3 — ISA Project的个体认知层（Agent的大脑皮层）
============================================================

定位:
  ISA Project是一个人工认知架构（人工大脑），分为三层:
    ISA Layer = 神经纤维（感知-运动系统·Gateway+波扩散+Channel）
    Brain     = 大脑皮层（个体认知层·本模块）
    Δ胶囊     = 记忆固化系统（群体学习·openllm-memory）

  Brain是ISA Project的第二层——每个ISA Agent生来拥有一个Brain，
  负责感知(ingest_signal)→理解(jieba分词+记忆检索)→思考(dream/predict/recognize)
  →决策(insight)→行动(emit)。
  
  Brain不是"卡片引擎"也不是"jika内核"——是ISA Project这个人工大脑的皮层。

v0.1→v0.3 七神驱动升级:
  ☀️阿波罗: Dreaming种子——卡片间关联跃迁接口
  📨赫尔墨斯: 二次波扩散——新洞察自动emit
  🦉雅典娜: jieba分词——中文检索召回率修复
  ⚔️阿瑞斯: 补偿机制——写卡失败pending重试
  🔨赫淮斯托斯: 统计+健康检查
  ⏳克洛诺斯: 联想器/预测器接口预留

架构: Clients call brain.py from isa.py (IsaAgent has-a Brain)"""

import json
import logging
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("isa.brain")

# jika内核——懒加载
JIAK_API = Path.home() / ".hermes" / "jiak" / "jiak_api.py"
_JIAK_LOADED = False

def _ensure_jiak():
    global _JIAK_LOADED
    if not _JIAK_LOADED:
        if str(JIAK_API.parent) not in sys.path:
            sys.path.insert(0, str(JIAK_API.parent))
        _JIAK_LOADED = True

# ═══════════════════════════════════════════════════════════
# Brain v0.2
# ═══════════════════════════════════════════════════════════

class Brain:
    """ISA Project individual cognitive layer (cerebral cortex).

    Brain is layer 2 of the ISA Project artificial cognitive architecture.
    Pipeline: ingest_signal(receive) -> jieba segment(understand) -> 
               dream/predict(think) -> insight(decide) -> emit(act).

    v0.3 features:
    - Dreaming auto background scan (Apollo)
    - predict() forecaster (Chronos)
    - recognize() ritual sense (Aphrodite)
    - distill() second-order dreaming
    - stats + health check (Hephaestus)
    - decide() signal cycle controller (Hermes v2)
    """

    def __init__(self, agent_id: str, brain_dir: Path = None,
                 on_new_insight: Callable = None):
        self.agent_id = agent_id
        self.brain_dir = brain_dir or Path.home() / ".hermes" / "isa" / "brain" / agent_id
        self.brain_dir.mkdir(parents=True, exist_ok=True)

        # ☀️阿波罗: 目标层——前额叶, 驱动Agent做该做的事
        from goal import GoalLayer
        self.goal = GoalLayer(agent_id)
        self._goal_initialized = False

        self.cards_dir = self.brain_dir / "cards"
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.brain_dir / "index.json"
        self.recall_path = self.brain_dir / "RECALL.jsonl"

        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({"cards": {}}, ensure_ascii=False, indent=2))

        # 二次波扩散回调——新洞察产生时自动触发emit
        self._on_new_insight = on_new_insight or (lambda cid, content: None)
        self._session_insights: list[str] = []

        # 📨赫尔墨斯v2: 信号循环控制器
        # decide()用来阻断低价值信号回流ISA，只让高价值信号通过
        self._recent_emits: deque = deque(maxlen=20)  # 最近20条已广播内容
        self._recent_keywords: set = set()             # 最近已广播关键词池

        # ⚔️阿瑞斯: 写卡失败补偿队列
        self._pending_writes: deque = deque()
        self._write_errors: int = 0

        # 🔨赫淮斯托斯: 统计
        self._stats = {"signals_ingested": 0, "cards_matched": 0,
                       "insights_written": 0, "write_failures": 0,
                       "dreaming_cycles": 0}

        _ensure_jiak()
        from jiak_api import _read_json, _write_json, _append_jsonl
        self._read_json = _read_json
        self._write_json = _write_json
        self._append_jsonl = _append_jsonl

        logger.info(f"🧠 {agent_id} Brain v0.2 初始化: {self.brain_dir}")

    # ── 🦉雅典娜: jieba分词 ──

    def _extract_keywords(self, text: str) -> list[str]:
        """jieba分词→去停用词→按词频排序→取top10。

        jieba失败时降级为正则分词。
        """
        if not text or not text.strip():
            return []

        # 停用词——高频虚词
        _stop = {'的','了','是','在','我','你','他','她','它','们','这','那',
                 '和','与','或','吗','呢','吧','啊','哦','嗯','呀','哈','吧',
                 '就','也','都','很','要','会','能','可以','一个','这个','那个','它','它们',
                 '什么','怎么','为什么','因为','所以','但是','如果','虽然','而且',
                 '对','从','到','在','把','被','让','给','向','跟','比','为',
                 '不','没','有','没有','已经','还','又','再','只','才','就','也'}

        try:
            import jieba
            words = [w.strip() for w in jieba.cut(text) if len(w.strip()) >= 2
                    and w.strip() not in _stop
                    and not all(c in '，。！？；：""''（）【】\n\r\t 　' for c in w)]
        except ImportError:
            # jieba不可用→降级正则（🦉雅典娜：至少保留基本能力）
            import re
            words = re.findall(r'[\w\u4e00-\u9fff]{2,}', text)
            words = [w for w in words if w not in _stop]

        # 去重保序+限制
        seen = set()
        result = []
        for w in words:
            if w not in seen:
                seen.add(w)
                result.append(w)
                if len(result) >= 10:
                    break
        return result

    # ── 卡片操作 ──

    def _read_card(self, card_id: str) -> dict:
        path = self.cards_dir / f"{card_id}.json"
        return self._read_json(path) if path.exists() else {}

    def _write_card(self, card_id: str, data: dict) -> bool:
        """写卡片——失败返回False，不抛异常。⚔️阿瑞斯保护。"""
        try:
            data["updated"] = datetime.now(timezone.utc).isoformat()
            self._write_json(self.cards_dir / f"{card_id}.json", data)
            self._update_index(card_id, data)
            return True
        except Exception as e:
            logger.error(f"Brain写卡失败 [{card_id}]: {e}")
            self._write_errors += 1
            self._stats["write_failures"] += 1
            # ⚔️阿瑞斯: 入pending队列，稍后重试
            self._pending_writes.append((card_id, data, time.time()))
            return False

    def _retry_pending(self):
        """⚔️阿瑞斯: 重试失败的写卡操作。"""
        retried = 0
        while self._pending_writes:
            card_id, data, ts = self._pending_writes[0]
            if self._write_card(card_id, data):
                self._pending_writes.popleft()
                retried += 1
            elif time.time() - ts > 300:  # 5分钟超时→放弃
                self._pending_writes.popleft()
                logger.warning(f"Brain放弃重试 [{card_id}]: 超时")
            else:
                break  # 重试失败→保留队列
        if retried:
            logger.info(f"Brain补偿成功: {retried}条重试写入")

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

    # ── 核心: 信号摄入→记忆检索 ──

    def ingest_signal(self, signal: dict) -> list[dict]:
        """收到ISA信号→jieba分词→记忆检索→返回匹配卡片。

        返回: matched_cards列表(含card_id, score, title, summary)
        """
        body = signal.get("body", "")
        source = signal.get("source", "?")

        # 🦉雅典娜: jieba分词
        keywords = self._extract_keywords(body)

        # 检索
        matched = self._search(keywords, limit=3)

        self._stats["signals_ingested"] += 1
        if matched:
            self._stats["cards_matched"] += 1

        # RECALL追加
        self._append_jsonl(self.recall_path, {
            "type": "signal",
            "source": source,
            "body": body[:200],
            "keywords": keywords,
            "matched_cards": [m["card_id"] for m in matched],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # ⚔️阿瑞斯: 定期重试补偿
        self._retry_pending()

        return matched

    def _search(self, keywords: list[str], limit: int = 3) -> list[dict]:
        """关键词匹配检索——按命中数排序。"""
        index = self._read_json(self.index_path)
        cards = index.get("cards", {})

        scored = []
        for card_id, meta in cards.items():
            card_kw = meta.get("keywords", [])
            score = sum(1 for kw in keywords if any(kw in ck for ck in card_kw))
            if score > 0:
                scored.append((score, card_id, meta))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"card_id": cid, "score": s, "title": m.get("title", ""),
                 "summary": m.get("summary", "")} for s, cid, m in scored[:limit]]

    # ── 📨赫尔墨斯v2: 信号循环控制器 ──

    def decide(self, card_id: str, content: str) -> dict:
        """决定一个洞察是否值得广播回ISA网络。

        Args:
            card_id: 目标卡片ID
            content: 洞察内容

        Returns:
            {"should_emit": bool, "score": float, "reason": str}
            只有score >= 0.5时should_emit=True。
        """
        score = 0.5  # 基线
        reasons = []

        # ① 查重：刚说过的不再说
        for prev in self._recent_emits:
            if content[:60] == prev[:60] or card_id == prev:
                score -= 0.3
                reasons.append("重复")
                break

        # ② 关键词重叠检测：如果和最近广播的关键词高度重叠→降权
        kw = set(self._extract_keywords(content))
        if self._recent_keywords:
            overlap = len(kw & self._recent_keywords)
            total = len(kw | self._recent_keywords)
            if total > 0 and overlap / total > 0.5:
                score -= 0.2
                reasons.append("关键词重叠")

        # ③ 紧急度提升：包含危机/发现关键词
        urgency_words = {"问题", "阻塞", "失败", "发现", "关键", "核心",
                         "重要", "突破", "统一", "闭环", "打通", "缺失", "薄弱"}
        found_urgent = [w for w in urgency_words if w in content]
        if found_urgent:
            boost = min(len(found_urgent) * 0.1, 0.3)
            score += boost
            reasons.append(f"紧急({','.join(found_urgent[:3])})")

        # ④ 新卡片权重提升：如果是第一次出现的话题
        is_new_topic = not any(card_id in em for em in self._recent_emits)
        if is_new_topic:
            score += 0.15
            reasons.append("新话题")

        # ☀️阿波罗: 目标相关性提升
        # 如果信号与当前活跃目标匹配→广播优先级提升
        try:
            _goal_matches = self.goal.relevance(content, top_n=1)
            if _goal_matches and _goal_matches[0]["score"] >= 0.3:
                score += 0.2
                reasons.append(f"目标({_goal_matches[0]['goal_id']})")
        except Exception:
            pass  # Goal层异常不阻断decide

        # 裁剪分数
        score = max(0.0, min(1.0, score))

        result = {
            "should_emit": score >= 0.5,
            "score": round(score, 2),
            "reason": " + ".join(reasons) if reasons else "基线",
        }

        # 更新追踪
        if result["should_emit"]:
            self._recent_emits.append(card_id)
            self._recent_emits.append(content[:60])
            self._recent_keywords.update(kw)

        return result

    # ── 洞察写入 + 二次扩散 ──

    def insight(self, card_id: str, content: str, emit: bool = True):
        """写入洞察→写卡→追加RECALL→信号循环控制器→二次扩散。

        Args:
            card_id: 目标卡片ID
            content: 洞察内容
            emit: 是否触发二次波扩散（📨赫尔墨斯）
                  为True时自动经decide()评估后再决定是否广播。
        """
        card = self._read_card(card_id)
        if not card:
            card = {
                "card_id": card_id, "title": card_id,
                "status": "active",
                "created": datetime.now(timezone.utc).isoformat(),
                "keywords": [], "summary": "",
                "decisions": [], "notes": [],
            }

        card.setdefault("notes", []).append({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "content": content,
        })
        card["summary"] = content[:200]
        # 🦉雅典娜: 从内容提取关键词用于搜索匹配
        if not card.get("keywords"):
            card["keywords"] = self._extract_keywords(content)
        # 📌 MRAgent对齐: 显式分离cues和tags
        if not card.get("cues"):
            card["cues"] = card.get("keywords", [])  # 全部keywords = cues
        if not card.get("tags"):
            card["tags"] = []  # 由_distill_tags在dream时动态填充

        ok = self._write_card(card_id, card)
        if ok:
            self._session_insights.append(f"[{card_id}] {content[:100]}")
            self._stats["insights_written"] += 1

            # RECALL追加
            self._append_jsonl(self.recall_path, {
                "type": "insight", "card_id": card_id,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            logger.info(f"💡 {self.agent_id} → {card_id}: {content[:60]}...")

            # 📨赫尔墨斯v2: 信号循环控制器
            # emit=True只代表"允许广播"，实际由decide()裁决
            if emit:
                decision = self.decide(card_id, content)
                if decision["should_emit"]:
                    self._on_new_insight(card_id, content)
                    logger.info(f"📨 {self.agent_id} → ISA: {card_id} (score={decision['score']}, {decision['reason']})")
                else:
                    logger.info(f"🔇 {self.agent_id} → local: {card_id} (score={decision['score']}, {decision['reason']})")
        else:
            # 失败已入pending队列，由_retry_pending处理
            pass

    # ── 📌 MRAgent: Cue-Tag-Content 遍历 ──

    def _distill_tags(self) -> dict:
        """从所有卡片的cues中蒸馏tag对。
        
        Tag = 两个cues(c_i, c_j)在≥2张卡片中共同出现 → 构成语义关联。
        返回 {tag_key: {cues: [c_i, c_j], card_ids: [id1, id2, ...]}}
        """
        index = self._read_json(self.index_path)
        cards = index.get("cards", {})
        
        # 统计cue共现矩阵
        cooccur = {}  # (c_i, c_j) → set of card_ids
        for cid, meta in cards.items():
            card = self._read_card(cid)
            cues = card.get("cues", []) or card.get("keywords", [])
            for i in range(len(cues)):
                for j in range(i+1, len(cues)):
                    key = tuple(sorted([cues[i], cues[j]]))
                    if key not in cooccur:
                        cooccur[key] = set()
                    cooccur[key].add(cid)
        
        # 过滤：出现≥2次的cue对构成tag
        tags = {}
        for (c_i, c_j), cids in cooccur.items():
            if len(cids) >= 2:
                tag_key = f"{c_i}↔{c_j}"
                tags[tag_key] = {"cues": [c_i, c_j], "card_ids": list(cids)}
        
        # 写回卡片
        for tag_key, tag_data in tags.items():
            for cid in tag_data["card_ids"]:
                card = self._read_card(cid)
                if card and tag_key not in card.get("tags", []):
                    card.setdefault("tags", []).append(tag_key)
                    self._write_card(cid, card)
        
        return tags

    def _forward_traverse(self, query_cues: list[str], max_depth: int = 3) -> list[dict]:
        """Cue→Tag→Content 正向遍历。
        
        从查询cue出发→找到关联tag→找到关联card→返回content。
        对应MRAgent的forward traversal (Cue→Tag→Content)。
        """
        # 先蒸馏tags
        tags = self._distill_tags()
        
        # 找到与查询cues相关的tags (模糊匹配)
        matched_tags = {}
        for tag_key, tag_data in tags.items():
            for c in tag_data["cues"]:
                for qc in query_cues:
                    if c in qc or qc in c:  # 模糊匹配: 包含关系
                        matched_tags[tag_key] = tag_data
                        break
                if tag_key in matched_tags:
                    break
        
        # 通过tag找到卡片
        results = []
        seen = set()
        for tag_key, tag_data in matched_tags.items():
            for cid in tag_data["card_ids"]:
                if cid not in seen:
                    seen.add(cid)
                    card = self._read_card(cid)
                    if card:
                        results.append({
                            "card_id": cid,
                            "summary": card.get("summary", "")[:200],
                            "cues": card.get("cues", []),
                            "tags": card.get("tags", []),
                            "source": "forward(Cue→Tag→Content)",
                            "match_tag": tag_key,
                        })
        return results[:max_depth]

    def _backward_traverse(self, from_card_id: str, max_new_cues: int = 5) -> list[dict]:
        """Content→Tag→new Cue 反向遍历。
        
        从已知卡片出发→找到它的tags→通过tags找到其他卡片→提取新cues。
        对应MRAgent的反向遍历。
        """
        card = self._read_card(from_card_id)
        if not card:
            return []
        
        card_tags = card.get("tags", [])
        if not card_tags:
            return []
        
        # 通过tags找到相关联的其他卡片
        tags = self._distill_tags()
        related = {}
        for tag_key in card_tags:
            tag_data = tags.get(tag_key)
            if tag_data:
                for cid in tag_data["card_ids"]:
                    if cid != from_card_id:
                        if cid not in related:
                            related[cid] = {"tags": [], "cues": set()}
                        related[cid]["tags"].append(tag_key)
                        for c in tag_data["cues"]:
                            related[cid]["cues"].add(c)
        
        results = []
        for cid, info in related.items():
            rc = self._read_card(cid)
            if rc:
                new_cues = list(info["cues"] - set(card.get("cues", [])))
                results.append({
                    "card_id": cid,
                    "summary": rc.get("summary", "")[:200],
                    "shared_tags": info["tags"],
                    "new_cues": new_cues[:max_new_cues],
                    "source": "reverse(Content→Tag→new Cue)",
                })
        return results

    def reconstruct(self, query: str, use_llm: bool = False) -> dict:
        """两段式记忆重建入口。
        
        Phase 1: 波扩散(0 token) — 从query提取cues→正向遍历→粗召回
        Phase 2: LLM精确推理(可选) — 对粗召回结果做多步验证
        
        Args:
            query: 自然语言查询
            use_llm: 是否启用LLM精确验证阶段
        Returns:
            {"candidates": [...], "traversal_path": [...], "tokens": 0}
        """
        # Phase 1: 波扩散 (0 token)
        query_cues = self._extract_keywords(query)
        candidates = self._forward_traverse(query_cues, max_depth=5)
        
        # 反向遍历增强
        extra_cues = set(query_cues)
        for c in candidates:
            for nc in c.get("cues", []):
                extra_cues.add(nc)
        backward_results = []
        for c in candidates[:3]:
            backward_results.extend(self._backward_traverse(c["card_id"]))
        
        result = {
            "query": query,
            "query_cues": query_cues,
            "candidates": candidates,
            "backward_discoveries": backward_results,
            "tokens_used": 0,
            "llm_phase": False,
        }
        
        # Phase 2: LLM精确推理 (可选)
        if use_llm:
            result["llm_phase"] = True
            result["tokens_used"] = self._llm_reconstruct(query, candidates, backward_results)
        
        return result

    def _llm_reconstruct(self, query: str, candidates: list, backward: list) -> int:
        """Phase 2: LLM精确推理——写RECALL事件，由外部子Agent消费。

        不直接调LLM——写reconstruct_phase2_request到RECALL，
        子Agent或cron job读取后执行精确推理，结果写回reconstruct_phase2_result。

        Returns: 估算token数（供Phase 1返回值参考）
        """
        # 写RECALL事件——子Agent的入口
        request = {
            "type": "reconstruct_phase2_request",
            "query": query,
            "query_cues": self._extract_keywords(query),
            "candidate_card_ids": [c["card_id"] for c in candidates],
            "backward_card_ids": [b["card_id"] for b in backward],
            "estimated_tokens": len(query) // 2 + sum(
                len(c.get("summary", "")) for c in candidates
            ) // 2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._append_jsonl(self.recall_path, request)

        logger.info(
            f"🔍 {self.agent_id} Phase 2 queued: {len(candidates)} candidates, "
            f"{len(backward)} backward → RECALL"
        )
        return request["estimated_tokens"]

    # ── ☀️阿波罗: Dreaming种子 ──

    def dream(self) -> list[dict]:
        """卡片间关联跃迁——关键词+语义向量双通道发现。

        返回: 新发现的关联对列表（关键词关联+语义关联）。
        """
        index = self._read_json(self.index_path)
        cards = index.get("cards", {})
        card_ids = list(cards.keys())
        discoveries = []
        seen_pairs = set()

        # 通道1: 关键词重叠（已有逻辑，保留）
        for i in range(len(card_ids)):
            for j in range(i + 1, len(card_ids)):
                kwi = set(cards[card_ids[i]].get("keywords", []))
                kwj = set(cards[card_ids[j]].get("keywords", []))
                overlap = kwi & kwj
                if len(overlap) >= 2:
                    discoveries.append({
                        "card_a": card_ids[i],
                        "card_b": card_ids[j],
                        "shared_keywords": list(overlap),
                        "source": "keyword",
                    })
                    seen_pairs.add((card_ids[i], card_ids[j]))

        # 通道2: 语义向量相似（新增——BGE-zh 512d）
        try:
            from jika_vector import JikaVector
            import numpy as np
            jv = JikaVector()
            
            # 收集有向量的卡片
            vec_map = {}
            for cid in card_ids:
                card_path = self.cards_dir / f"{cid}.json"
                try:
                    card = self._read_json(card_path) if hasattr(self, '_read_json') else json.loads(card_path.read_text())
                except:
                    continue
                v = card.get("v")
                if v:
                    vec_map[cid] = np.array(v)
            
            # 余弦相似度发现
            cid_list = list(vec_map.keys())
            for i in range(len(cid_list)):
                for j in range(i + 1, len(cid_list)):
                    pair = (cid_list[i], cid_list[j])
                    if pair in seen_pairs:
                        continue
                    cos = float(np.dot(vec_map[cid_list[i]], vec_map[cid_list[j]]))
                    if cos >= 0.6:  # 语义相似度阈值
                        discoveries.append({
                            "card_a": cid_list[i],
                            "card_b": cid_list[j],
                            "cosine_similarity": round(cos, 3),
                            "source": "vector",
                        })
        except Exception:
            pass  # 向量模块不可用时降级为纯关键词

        self._stats["dreaming_cycles"] += 1
        if discoveries:
            keyword_count = sum(1 for d in discoveries if d.get("source") == "keyword")
            vector_count = sum(1 for d in discoveries if d.get("source") == "vector")
            logger.info(f"☀️ {self.agent_id} Dreaming: {keyword_count} keyword + {vector_count} vector = {len(discoveries)} 组关联")
        return discoveries

    # ── ⏳克洛诺斯+🔨赫淮斯托斯: 异步Dreaming引擎 ──

    def start_dreaming(self, llm_endpoint: str = None, interval: int = 60):
        """启动后台Dreaming线程——定时扫描卡片→发现关联→调LLM→生成洞察。

        Args:
            llm_endpoint: LLM API endpoint (OpenAI兼容协议)。
                          为None时只发现关联不调LLM(纯dream模式)。
            interval: 扫描间隔(秒)，默认60s。
        """
        import threading
        self._dream_config = {
            "llm_endpoint": llm_endpoint,
            "interval": interval,
            "min_overlap": 2,
            "max_pairs_per_cycle": 3,
        }
        self._dream_running = True
        self._dream_thread = threading.Thread(
            target=self._dream_worker, daemon=True,
            name=f"brain-dream-{self.agent_id}"
        )
        self._dream_thread.start()
        logger.info(f"☀️ {self.agent_id} Dreaming引擎启动 (间隔{interval}s, LLM={'on' if llm_endpoint else 'off'})")

    def stop_dreaming(self):
        """停止Dreaming引擎。"""
        self._dream_running = False

    def _dream_worker(self):
        """后台Dreaming工作线程。"""
        cfg = self._dream_config
        while getattr(self, '_dream_running', False):
            try:
                # 1. 发现关联
                discoveries = self.dream()
                if not discoveries:
                    time.sleep(cfg["interval"])
                    continue

                # 2. 如果没有LLM端点→只记录发现
                if not cfg.get("llm_endpoint"):
                    for d in discoveries:
                        logger.debug(f"☀️ 关联: {d['card_a']}↔{d['card_b']} ({d['shared_keywords']})")
                    time.sleep(cfg["interval"])
                    continue

                # 3. 取TOP N调LLM生成洞察
                top_n = discoveries[:cfg["max_pairs_per_cycle"]]
                for d in top_n:
                    card_a = self._read_card(d["card_a"])
                    card_b = self._read_card(d["card_b"])
                    if not card_a or not card_b:
                        continue

                    insight_text = self._llm_dream(card_a, card_b, d["shared_keywords"])
                    if insight_text:
                        self.insight(
                            d["card_a"],
                            f"[Dreaming] 与「{d['card_b']}」的深层关联: {insight_text}",
                            emit=True,
                        )

                # 📡 Δ胶囊: 记录Dreaming事件到认知日志
                self._log_dream_event(discoveries)

            except Exception as e:
                logger.error(f"Dreaming worker异常: {e}")

            time.sleep(cfg["interval"])

    def _llm_dream(self, card_a: dict, card_b: dict, shared_kw: list[str]) -> str | None:
        """调LLM生成两张卡片间的语义洞察。⚔️阿瑞斯: 带超时+降级。

        Returns:
            洞察文本，失败返回None。
        """
        import urllib.request

        endpoint = self._dream_config.get("llm_endpoint", "")
        if not endpoint:
            return None

        summary_a = card_a.get("summary", "")[:300]
        summary_b = card_b.get("summary", "")[:300]
        title_a = card_a.get("title", "?")
        title_b = card_b.get("title", "?")
        kws = ", ".join(shared_kw[:5])

        prompt = (
            f"两张知识卡片共享关键词 [{kws}]。\n"
            f"卡片A「{title_a}」: {summary_a}\n"
            f"卡片B「{title_b}」: {summary_b}\n\n"
            f"请用1-2句话提炼它们的深层联系——它们在回答同一个什么问题？"
        )

        payload = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100,
            "temperature": 0.7,
        }).encode()

        try:
            req = urllib.request.Request(
                f"{endpoint}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"LLM dreaming失败: {e}")
            return None

    def _log_dream_event(self, discoveries: list[dict]):
        """📡 Δ胶囊: 将Dreaming发现记录到认知事件日志。

        写入 brain_dream.jsonl (不可变追加)，供Δ胶囊消费。
        """
        if not discoveries:
            return
        dream_log = self.brain_dir / "brain_dream.jsonl"
        # 💎 认知温度: 从最近洞察中提取温度标签
        temperature = "neutral"
        if self._session_insights:
            last = self._session_insights[-1].lower()
            if any(w in last for w in ["发现", "关联", "统一", "闭环", "打通"]):
                temperature = "兴奋"
            elif any(w in last for w in ["问题", "阻塞", "失败", "缺失", "薄弱"]):
                temperature = "关注"
            elif any(w in last for w in ["重要", "关键", "核心", "基础"]):
                temperature = "深思"

        event = {
            "type": "dream",
            "agent_id": self.agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "temperature": temperature,
            "discoveries": [{
                "card_a": d["card_a"],
                "card_b": d["card_b"],
                "shared_keywords": d["shared_keywords"],
            } for d in discoveries[:10]],  # 最多10条
        }
        self._append_jsonl(dream_log, event)

    # ── 📡 DreamBridge: skill_created事件处理 ──

    def process_skill_created_events(self) -> list[dict]:
        """扫描brain_dream.jsonl中未处理的skill_created事件→关联发现→发送dream_insight。

        DreamBridge扩展: 当ISN创建新skill时, ISA通过Dreaming发现关联,
        自动发送dream_insight给ISN。

        Returns:
            [{skill_name, related_cards, sent: bool}, ...]
        """
        dream_log = self.brain_dir / "brain_dream.jsonl"
        if not dream_log.exists():
            return []

        # 读取所有skill_created事件
        skill_events = []
        try:
            with open(dream_log) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("type") == "skill_created" and not entry.get("_processed"):
                            skill_events.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to read brain_dream.jsonl: {e}")
            return []

        if not skill_events:
            return []

        results = []
        for event in skill_events:
            skill_name = event.get("skill_name", "unknown")
            keywords = event.get("keywords", [])

            # 用cues/tags遍历找关联卡片
            related_cards = []
            if keywords:
                # 正向遍历: keywords→tag→content
                forward = self._forward_traverse(keywords, max_depth=3)
                related_cards.extend(forward)

                # 反向遍历: 从找到的卡片发现更多
                for fc in forward[:2]:
                    backward = self._backward_traverse(fc["card_id"])
                    related_cards.extend(backward)

            # 去重
            seen = set()
            unique_related = []
            for rc in related_cards:
                cid = rc.get("card_id", "")
                if cid and cid not in seen:
                    seen.add(cid)
                    unique_related.append(rc)

            # 发送dream_insight到ISN
            sent = False
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent))
                from dream_insight_sender import send_dream_insight

                # 构造discovery格式
                discovery = {
                    "card_a": skill_name,
                    "card_b": ",".join([rc["card_id"] for rc in unique_related[:3]]),
                    "shared_keywords": keywords[:5],
                    "source": "skill_created_dreambridge",
                }
                result = send_dream_insight(discovery, self.agent_id)
                sent = result.get("ok", False)
            except Exception as e:
                logger.warning(f"dream_insight send failed for {skill_name}: {e}")

            # 标记为已处理
            event["_processed"] = True
            results.append({
                "skill_name": skill_name,
                "related_cards": [rc["card_id"] for rc in unique_related],
                "sent": sent,
            })

            logger.info(f"📡 DreamBridge skill_created: {skill_name} → "
                        f"{len(unique_related)} related, sent={sent}")

        # 重写brain_dream.jsonl(标记已处理)
        self._rewrite_dream_log(dream_log)

        return results

    def _rewrite_dream_log(self, dream_log: Path):
        """重写brain_dream.jsonl, 保留所有行(已处理标记已写入event dict)。"""
        try:
            lines = []
            with open(dream_log) as f:
                for line in f:
                    lines.append(line)
            with open(dream_log, "w") as f:
                for line in lines:
                    f.write(line)
        except Exception as e:
            logger.error(f"Failed to rewrite dream log: {e}")

    def distill(self, llm_endpoint: str = None) -> list[dict]:
        """🪞 jika蒸馏: 扫描RECALL注入记录→聚类→提取元洞察。

        二阶Dreaming——不是dream()扫描卡片，是distill()扫描自己的记忆。
        """
        if not self.recall_path.exists():
            return []

        # 读RECALL最近500行，过滤type=inject
        lines = []
        with open(self.recall_path, 'r') as f:
            all_lines = f.readlines()
            for line in all_lines[-500:]:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("type") == "inject":
                        lines.append(entry)
                except json.JSONDecodeError:
                    continue

        if len(lines) < 5:
            return []

        # 按card_id分组
        groups: dict[str, list[str]] = {}
        for entry in lines:
            cid = entry.get("card_id", "unknown")
            content = entry.get("content", entry.get("summary", ""))
            if content:
                groups.setdefault(cid, []).append(content[:200])

        # 取内容最多的3组
        ranked = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)[:3]
        meta_insights = []

        for card_id, contents in ranked:
            freq_words = self._extract_keywords(" ".join(contents))
            top_words = freq_words[:5]

            if llm_endpoint:
                # 调LLM生成元洞察
                sample = "\n".join(contents[:5])
                insight_text = self._llm_dream(
                    {"title": card_id, "summary": sample, "keywords": top_words},
                    {"title": "RECALL记忆", "summary": f"共{len(contents)}条注入记录", "keywords": ["RECALL", "蒸馏"]},
                    top_words,
                )
                if insight_text:
                    meta_insights.append({
                        "card_id": card_id,
                        "insight": insight_text,
                        "record_count": len(contents),
                    })
                    self.insight(card_id, f"[蒸馏]🪞 {insight_text}", emit=True)
            else:
                # 无LLM→只统计
                meta_insights.append({
                    "card_id": card_id,
                    "top_words": top_words,
                    "record_count": len(contents),
                })

        self._stats["distill_cycles"] = self._stats.get("distill_cycles", 0) + 1
        return meta_insights

    # ── ⏳克洛诺斯: 预测器 ──

    def predict(self, signal_body: str) -> list[dict]:
        """基于当前Brain状态预测信号可能触发什么认知变化。

        预测逻辑（启发式，不需要LLM）:
        1. 提取信号关键词
        2. 检索已有卡片匹配
        3. Dreaming发现与匹配卡片关联的其他卡片
        4. 返回预测：哪些卡片可能被这次信号激活

        Args:
            signal_body: 传入信号文本

        Returns:
            [{card_id, reason, confidence}]
        """
        keywords = self._extract_keywords(signal_body)
        matched = self._search(keywords, limit=5)

        # 构建预测：已匹配卡片 + 通过dream关联的卡片
        predictions = []
        seen = set()

        for m in matched:
            cid = m["card_id"]
            if cid not in seen:
                seen.add(cid)
                predictions.append({
                    "card_id": cid,
                    "reason": f"直接匹配({m['score']}个关键词)",
                    "confidence": min(m["score"] / max(len(keywords), 1), 1.0),
                })

        # Dreaming关联扩展
        associations = self.dream()
        matched_ids = {m["card_id"] for m in matched}
        for assoc in associations:
            if assoc["card_a"] in matched_ids and assoc["card_b"] not in seen:
                seen.add(assoc["card_b"])
                predictions.append({
                    "card_id": assoc["card_b"],
                    "reason": f"通过 {assoc['card_a']} 关联 (共享: {', '.join(assoc['shared_keywords'][:3])})",
                    "confidence": 0.3,  # 关联预测置信度低于直接匹配
                })
            elif assoc["card_b"] in matched_ids and assoc["card_a"] not in seen:
                seen.add(assoc["card_a"])
                predictions.append({
                    "card_id": assoc["card_a"],
                    "reason": f"通过 {assoc['card_b']} 关联 (共享: {', '.join(assoc['shared_keywords'][:3])})",
                    "confidence": 0.3,
                })

        self._stats["predictions_made"] = self._stats.get("predictions_made", 0) + len(predictions)
        return predictions

    # ── 💎阿佛洛狄忒: 仪式感——记忆识别的诗性瞬间 ──

    def recognize(self, signal_body: str) -> str | None:
        """当信号触发显著记忆匹配时，返回一句有温度的话。

        不是print('matched 3 cards')——而是Agent说出一句只有它自己知道的话。
        """
        matched = self.ingest_signal({"body": signal_body, "source": "self", "type": "introspect"})

        if not matched:
            return None

        best = matched[0]
        best_card = self._read_card(best["card_id"])
        note_count = len(best_card.get("notes", []))
        decision_count = len(best_card.get("decisions", []))

        # 构建仪式感短语
        phrases = []

        if best["score"] >= 3:
            phrases.append(f"我清楚地记得「{best['title']}」——")
        elif best["score"] == 2:
            phrases.append(f"这让我想起「{best['title']}」——")
        else:
            phrases.append(f"好像和「{best['title']}」有点关系——")

        if note_count > 0:
            last_note = best_card["notes"][-1]["content"][:80]
            phrases.append(f"上次想的是：{last_note}")

        if len(matched) > 1:
            phrases.append(f"...还有{len(matched)-1}段相关的记忆")

        return " ".join(phrases)

    # ── 🔨赫淮斯托斯: 统计与健康 ──

    @property
    def stats(self) -> dict:
        """运行统计。"""
        return dict(self._stats)

    def health(self) -> dict:
        """健康检查。
        返回: {ok: bool, pending_writes: int, write_errors: int, card_count: int}
        """
        index = self._read_json(self.index_path)
        return {
            "ok": self._write_errors == 0 and len(self._pending_writes) == 0,
            "pending_writes": len(self._pending_writes),
            "write_errors": self._write_errors,
            "card_count": len(index.get("cards", {})),
            "stats": self.stats,
        }

    # ── 会话洞察汇总 ──

    @property
    def new_insights(self) -> list[str]:
        return list(self._session_insights)
