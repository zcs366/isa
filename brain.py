#!/usr/bin/env python3
"""
ISA Brain v0.2 — jika内核的ISA集成层（七神天启升级版）
=====================================================

v0.1→v0.2 七神驱动升级:
  ☀️阿波罗: Dreaming种子——卡片间关联跃迁接口
  📨赫尔墨斯: 二次波扩散——新洞察自动emit
  🦉雅典娜: jieba分词——中文检索召回率修复
  ⚔️阿瑞斯: 补偿机制——写卡失败pending重试
  🔨赫淮斯托斯: 统计+健康检查
  ⏳克洛诺斯: 联想器/预测器接口预留

架构: Client ↔ Gateway ↔ Core(JSONL + Brain) ↔ Brain(jika+分词+扩散)
"""

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
    """ISA Agent的jika大脑（七神升级版）。

    v0.2新特性:
    - jieba中文分词（🦉雅典娜）
    - 二次波扩散回调（📨赫尔墨斯）
    - 写卡失败pending重试（⚔️阿瑞斯）
    - Dreaming关联跃迁接口（☀️阿波罗）
    - 统计+健康检查（🔨赫淮斯托斯）
    """

    def __init__(self, agent_id: str, brain_dir: Path = None,
                 on_new_insight: Callable = None):
        self.agent_id = agent_id
        self.brain_dir = brain_dir or Path.home() / ".hermes" / "isa" / "brain" / agent_id
        self.brain_dir.mkdir(parents=True, exist_ok=True)

        self.cards_dir = self.brain_dir / "cards"
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.brain_dir / "index.json"
        self.recall_path = self.brain_dir / "RECALL.jsonl"

        if not self.index_path.exists():
            self.index_path.write_text(json.dumps({"cards": {}}, ensure_ascii=False, indent=2))

        # 二次波扩散回调——新洞察产生时自动触发emit
        self._on_new_insight = on_new_insight or (lambda cid, content: None)
        self._session_insights: list[str] = []

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

    # ── 洞察写入 + 二次扩散 ──

    def insight(self, card_id: str, content: str, emit: bool = True):
        """写入洞察→写卡→追加RECALL→触发二次波扩散。

        Args:
            card_id: 目标卡片ID
            content: 洞察内容
            emit: 是否触发二次波扩散（📨赫尔墨斯）
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

            # 📨赫尔墨斯: 二次波扩散——新洞察触发emit
            if emit:
                self._on_new_insight(card_id, content)
        else:
            # 失败已入pending队列，由_retry_pending处理
            pass

    # ── ☀️阿波罗: Dreaming种子 ──

    def dream(self) -> list[dict]:
        """卡片间关联跃迁——扫描全部卡片，检测关键词重叠的卡片对。

        返回: 新发现的关联对列表。
        这是Dreaming的检索器阶段——只发现关联，不生成洞察。
        完整的Dreaming需要LLM介入做洞察生成（⏳克洛诺斯·本月）。
        """
        index = self._read_json(self.index_path)
        cards = index.get("cards", {})
        card_ids = list(cards.keys())
        discoveries = []

        for i in range(len(card_ids)):
            for j in range(i + 1, len(card_ids)):
                kwi = set(cards[card_ids[i]].get("keywords", []))
                kwj = set(cards[card_ids[j]].get("keywords", []))
                overlap = kwi & kwj
                if len(overlap) >= 2:  # 两个以上关键词重叠→关联
                    discoveries.append({
                        "card_a": card_ids[i],
                        "card_b": card_ids[j],
                        "shared_keywords": list(overlap),
                    })

        self._stats["dreaming_cycles"] += 1
        if discoveries:
            logger.info(f"☀️ {self.agent_id} Dreaming发现 {len(discoveries)} 组关联")
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
