"""
ISA Arbiter v0.1 — ISA Project的认知仲裁层（阿瑞斯）。

定位:
  ISA Project认知架构中，当多个Agent的dream/insight产生冲突时，
  Arbiter负责检测矛盾、裁定真相、维护认知一致性。

  不是"谁对谁错"——是"矛盾是否真实、如何调和、记录分歧"。

认知冲突来源:
  - AgentA dream: "ISA是管道" ↔ AgentB dream: "ISA是大脑"
  - Δ胶囊同时存储了矛盾的认知
  - 新旧知识冲突（v0.1认为X，v0.8证明非X）

仲裁结果:
  - RESOLVED: 可调和（如"ISA既是管道又是大脑——取决于层次"）
  - CONTRADICTION: 真矛盾（如设计决策分歧，需外部裁决）
  - STALEMATE: 证据不足，标记待定
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from collections import defaultdict


# ── 仲裁裁决类型 ──

RESOLVED = "resolved"        # 可调和
CONTRADICTION = "contradiction"  # 真矛盾
STALEMATE = "stalemate"      # 证据不足


# ── 仲裁器 ──

class Arbiter:
    """ISA Project认知仲裁层。

    检测→分析→裁定→记录矛盾认知，维护Agent社会的认知一致性。
    """

    def __init__(self, arbiter_dir: Optional[Path] = None):
        self.arbiter_dir = arbiter_dir or Path.home() / ".hermes" / "isa" / "arbiter"
        self.arbiter_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.arbiter_dir / "arbitrations.jsonl"
        self._load_cache()

    def _load_cache(self):
        """加载缓存：所有已知裁定"""
        self._rulings: dict[tuple[str, str], dict] = {}
        if self.log_path.exists():
            with open(self.log_path, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        key = (entry.get("topic_a", ""), entry.get("topic_b", ""))
                        self._rulings[key] = entry
                        # Also store reverse key
                        self._rulings[(entry.get("topic_b", ""), entry.get("topic_a", ""))] = entry
                    except (json.JSONDecodeError, KeyError):
                        continue

    # ── 矛盾检测 ──

    def detect_conflicts(self, insights: list[dict]) -> list[dict]:
        """检测一组insight中是否存在认知矛盾。

        Args:
            insights: [{"agent_id": str, "card_id": str, "content": str, "timestamp": str}, ...]

        Returns:
            [{"topic_a": str, "topic_b": str, 
              "claims": [{"agent": str, "claim": str}, ...],
              "severity": float,  # 0-1 矛盾严重度
              }, ...]
        """
        # 按card_id分组
        by_card: dict[str, list] = defaultdict(list)
        for ins in insights:
            by_card[ins.get("card_id", "unknown")].append(ins)

        conflicts = []
        for card_id, claims in by_card.items():
            if len(claims) < 2:
                continue

            # 同一卡片上的矛盾: 不同Agent说不同内容
            unique_claims = set()
            claim_sources = []
            for c in claims:
                snippet = c.get("content", "")[:80]
                if snippet not in unique_claims:
                    unique_claims.add(snippet)
                    claim_sources.append({
                        "agent": c.get("agent_id", "?"),
                        "claim": snippet,
                        "timestamp": c.get("timestamp", ""),
                    })

            if len(unique_claims) >= 2:
                # 检查是否有已知裁定
                existing = self._rulings.get((card_id, ""), None)
                severity = min(len(unique_claims) * 0.25, 1.0)

                conflicts.append({
                    "topic_a": card_id,
                    "topic_b": card_id,
                    "claims": claim_sources,
                    "severity": round(severity, 2),
                    "previously_ruled": existing is not None,
                    "prior_ruling": existing.get("verdict") if existing else None,
                })

        return conflicts

    # ── 仲裁 ──

    def arbitrate(self, conflict: dict) -> dict:
        """仲裁一个认知矛盾。

        裁决逻辑:
          1. 如果已有裁定→返回已有裁定
          2. 如果只有两个claim→检查是否能调和
          3. 多个claim→多数决（由外部仲裁者裁定）
          4. 无法断定→标记为STALEMATE

        Args:
            conflict: detect_conflicts()输出的矛盾

        Returns:
            {"topic_a": str, "topic_b": str,
             "verdict": RESOLVED|CONTRADICTION|STALEMATE,
             "resolution": str,  # 仲裁结果描述
             "confidence": float,  # 0-1 置信度
             "arbitrated_at": str,  # ISO时间
            }
        """
        # 检查缓存
        key = (conflict.get("topic_a", ""), conflict.get("topic_b", ""))
        if key in self._rulings:
            return self._rulings[key]

        claims = conflict.get("claims", [])
        if not claims:
            return self._stalemate(conflict, "无claim")

        # 提取主张关键词
        topics_seen = set()
        for c in claims:
            # 简单启发: 检查claim是否描述同一事物的不同方面
            claim_lower = c["claim"].lower()
            topics_seen.add(claim_lower[:40])

        # 裁决启发式逻辑
        if len(topics_seen) == 1:
            # 实际上没矛盾——表述不同但意思相同
            resolution = "表述差异无实质矛盾: " + list(topics_seen)[0][:60]
            return self._record(key, RESOLVED, resolution, 0.9, claims)

        elif len(topics_seen) == 2:
            t1, t2 = list(topics_seen)[:2]
            # 检查是否能调和（比如"是A"和"是B"但A和B可能共存）
            if self._is_reconcilable(t1, t2):
                resolution = f"可调和: 「{t1[:40]}」与「{t2[:40]}」可以共存——取决于上下文"
                return self._record(key, RESOLVED, resolution, 0.7, claims)
            else:
                resolution = f"真矛盾: 「{t1[:40]}」与「{t2[:40]}」不能同时为真, 需@军师裁定"
                return self._record(key, CONTRADICTION, resolution, 0.5, claims)

        else:
            # 三个以上不同主张 → 真分歧
            agents = ", ".join(c["agent"] for c in claims[:3])
            resolution = f"多方分歧({len(claims)}个主张): {agents}等, 需@军师汇集裁定"
            return self._record(key, CONTRADICTION, resolution, 0.4, claims)

    def _is_reconcilable(self, claim1: str, claim2: str) -> bool:
        """判断两个claim是否可能调和（共存）。"""
        # 调和模式: "是X" vs "是Y" 但X和Y可能都是同一事物的不同方面
        reconcilable_pairs = [
            ("管道", "大脑"), ("神经", "皮层"), ("存储", "认知"),
            ("接口", "实现"), ("协议", "架构"), ("短期", "长期"),
            ("个体", "群体"), ("实时", "离线"), ("本地", "全局"),
        ]
        for a, b in reconcilable_pairs:
            if (a in claim1 and b in claim2) or (b in claim1 and a in claim2):
                return True
        return False

    def _record(self, key: tuple, verdict: str, resolution: str,
                confidence: float, claims: list) -> dict:
        """记录并持久化仲裁结果。"""
        entry = {
            "topic_a": key[0],
            "topic_b": key[1] if len(key) > 1 else key[0],
            "verdict": verdict,
            "resolution": resolution,
            "confidence": round(confidence, 2),
            "claim_count": len(claims),
            "agents": list(set(c["agent"] for c in claims)),
            "arbitrated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._append_log(entry)
        self._rulings[key] = entry
        return entry

    def _stalemate(self, conflict: dict, reason: str) -> dict:
        key = (conflict.get("topic_a", ""), conflict.get("topic_b", ""))
        return self._record(key, STALEMATE, f"证据不足: {reason}", 0.0, [])

    def _append_log(self, entry: dict):
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── 查询 ──

    def unresolved(self) -> list[dict]:
        """列出所有未解决的矛盾（CONTRADICTION和STALEMATE）。"""
        results = []
        for key, ruling in self._rulings.items():
            if ruling["verdict"] in (CONTRADICTION, STALEMATE):
                # 去重（同一个ruling可能以两个key存储）
                if not any(r.get("_id") == id(ruling) for r in results):
                    results.append(ruling)
        return results

    def stats(self) -> dict:
        """仲裁统计。"""
        counts = defaultdict(int)
        for ruling in self._rulings.values():
            counts[ruling["verdict"]] += 1
        return {
            "total_rulings": len(self._rulings),
            "resolved": counts.get(RESOLVED, 0),
            "contradictions": counts.get(CONTRADICTION, 0),
            "stalemates": counts.get(STALEMATE, 0),
        }


def cli():
    """CLI: python3 -m arbiter [detect|unresolved|stats]"""
    import sys
    arbiter = Arbiter()

    if len(sys.argv) < 2:
        print("用法: python3 -m arbiter [detect|unresolved|stats]")
        return

    cmd = sys.argv[1]

    if cmd == "detect":
        # 从stdin或参数读取insight JSON
        if not sys.stdin.isatty():
            insights = json.load(sys.stdin)
        else:
            insights = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
        conflicts = arbiter.detect_conflicts(insights)
        if conflicts:
            print(f"发现 {len(conflicts)} 个矛盾:")
            for c in conflicts:
                print(f"  ⚔️ {c['topic_a']}: {len(c['claims'])}个claim, 严重度{c['severity']}")
                ruling = arbiter.arbitrate(c)
                print(f"    裁决: {ruling['verdict']} — {ruling['resolution'][:60]}")
        else:
            print("无矛盾")

    elif cmd == "unresolved":
        problems = arbiter.unresolved()
        if problems:
            print(f"{len(problems)} 个未解决矛盾:")
            for p in problems:
                print(f"  ⚠️ {p['topic_a']} ↔ {p['topic_b']}: {p['resolution'][:60]}")
        else:
            print("无未解决矛盾 ✅")

    elif cmd == "stats":
        s = arbiter.stats()
        print(f"仲裁统计: 总计{s['total_rulings']} "
              f"✅已调{s['resolved']} ⚔️矛盾{s['contradictions']} ⏳待定{s['stalemates']}")


if __name__ == "__main__":
    cli()
