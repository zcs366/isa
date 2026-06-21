"""
ISA Goal v0.1 — ISA Project的目标层（阿波罗：前额叶）。

定位:
  整个ISA Project认知架构中唯一回答"为什么"的层。
  ISA(神经)问"什么信号", Brain(皮层)问"怎么处理",
  Δ胶囊(记忆)问"过去如何", Arbiter问"矛盾何在",
  Offline问"断了怎么办"——只有Goal问"我们要什么"。

三层目标体系:
  HIGH  = 核心使命（不变·如"建立人类级通用认知架构"）
  MID   = 当前攻关（月度·如"完成关5世界建模"）
  LOW   = 实时意图（会话级·如"验证Dreaming数据闭环"）

认知循环中的Goal:
  信号进来 → Brain处理 → Goal评估相关性 → 
  高相关→深度处理(Δ胶囊+Arbiter) | 低相关→浅处理(Brain→ISA)
  Goal决定Agent做什么——不是被动响应信号，是主动追求目标。
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable
from enum import Enum


class Priority(Enum):
    HIGH = "high"     # 核心使命——不变
    MID = "mid"       # 当前攻关——月度
    LOW = "low"       # 实时意图——会话级


class Status(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Goal:
    """一个目标——ISA Project认知架构中驱动行为的意图单元。"""

    def __init__(self, goal_id: str, title: str, description: str,
                 priority: Priority, keywords: list[str] = None,
                 parent: Optional[str] = None):
        self.goal_id = goal_id
        self.title = title
        self.description = description
        self.priority = priority
        self.keywords = keywords or []
        self.parent = parent
        self.status = Status.ACTIVE
        self.created = datetime.now(timezone.utc).isoformat()
        self.progress: float = 0.0  # 0.0-1.0
        self.notes: list[str] = []

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id, "title": self.title,
            "description": self.description, "priority": self.priority.value,
            "keywords": self.keywords, "parent": self.parent,
            "status": self.status.value,
            "created": self.created, "progress": self.progress,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        g = cls(d["goal_id"], d.get("title", ""), d.get("description", ""),
                Priority(d.get("priority", "low")), d.get("keywords", []),
                d.get("parent"))
        g.status = Status(d.get("status", "active"))
        g.created = d.get("created", g.created)
        g.progress = d.get("progress", 0.0)
        g.notes = d.get("notes", [])
        return g


class GoalLayer:
    """ISA Project目标层——前额叶。

    管理目标的层次结构（HIGH→MID→LOW），
    评估信号与目标的相关性，驱动Agent做该做的事。
    """

    def __init__(self, agent_id: str, goals_dir: Optional[Path] = None):
        self.agent_id = agent_id
        self.goals_dir = (goals_dir or 
            Path.home() / ".hermes" / "isa" / "goals" / agent_id)
        self.goals_dir.mkdir(parents=True, exist_ok=True)
        self.goals_path = self.goals_dir / "goals.json"
        self._goals: dict[str, Goal] = {}
        self._load()

    def _load(self):
        if self.goals_path.exists():
            try:
                data = json.loads(self.goals_path.read_text())
                self._goals = {gid: Goal.from_dict(g) 
                              for gid, g in data.get("goals", {}).items()}
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        data = {
            "agent_id": self.agent_id,
            "updated": datetime.now(timezone.utc).isoformat(),
            "goals": {gid: g.to_dict() for gid, g in self._goals.items()},
        }
        self.goals_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # ── 目标管理 ──

    def add(self, goal_id: str, title: str, description: str,
            priority: Priority = Priority.LOW, keywords: list[str] = None,
            parent: str = None) -> Goal:
        goal = Goal(goal_id, title, description, priority, keywords, parent)
        self._goals[goal_id] = goal
        self._save()
        return goal

    def update(self, goal_id: str, **kwargs):
        if goal_id in self._goals:
            goal = self._goals[goal_id]
            for k, v in kwargs.items():
                if hasattr(goal, k):
                    setattr(goal, k, v)
            self._save()

    def complete(self, goal_id: str):
        self.update(goal_id, status=Status.COMPLETED, progress=1.0)

    def pause(self, goal_id: str):
        self.update(goal_id, status=Status.PAUSED)

    def activate(self, goal_id: str):
        self.update(goal_id, status=Status.ACTIVE)

    def active_goals(self, priority: Priority = None) -> list[Goal]:
        goals = [g for g in self._goals.values() if g.status == Status.ACTIVE]
        if priority:
            goals = [g for g in goals if g.priority == priority]
        return sorted(goals, key=lambda g: (
            {"high": 0, "mid": 1, "low": 2}[g.priority.value],
            -g.progress
        ))

    # ── 相关性评估 ──

    def relevance(self, content: str, top_n: int = 3) -> list[dict]:
        """评估一段内容(信号/洞察)与当前目标的匹配度。

        Returns:
            [{"goal_id": str, "score": float, "matched_keywords": [...]}, ...]
        """
        scores = []
        for g in self.active_goals():
            if not g.keywords:
                continue
            hits = [kw for kw in g.keywords if kw in content]
            if hits:
                score = len(hits) / max(len(g.keywords), 1)
                scores.append({
                    "goal_id": g.goal_id,
                    "title": g.title,
                    "score": round(score, 2),
                    "matched_keywords": hits,
                })
        return sorted(scores, key=lambda x: -x["score"])[:top_n]

    def should_deep_process(self, content: str, threshold: float = 0.3) -> bool:
        """判断一个信号是否值得深度处理(进Δ胶囊+Arbiter)。

        如果与某个活跃目标的相关性超过阈值→深度处理。
        """
        return any(r["score"] >= threshold for r in self.relevance(content))

    # ── 统计 ──

    def stats(self) -> dict:
        counts = {s.value: 0 for s in Status}
        priorities = {p.value: 0 for p in Priority}
        for g in self._goals.values():
            counts[g.status.value] = counts.get(g.status.value, 0) + 1
            priorities[g.priority.value] = priorities.get(g.priority.value, 0) + 1
        return {
            "total": len(self._goals),
            "by_status": counts,
            "by_priority": priorities,
            "active": [{"id": g.goal_id, "title": g.title, "priority": g.priority.value}
                      for g in self.active_goals()],
        }


def cli():
    """CLI: python3 -m goal [add|list|complete|relevance]"""
    import sys
    agent = sys.argv[2] if len(sys.argv) > 2 else "军师"
    gl = GoalLayer(agent)

    if len(sys.argv) < 2:
        print("用法: python3 -m goal [init|list|relevance <内容>]")
        return

    cmd = sys.argv[1]

    if cmd == "init":
        # 初始目标设定
        gl.add("architect-cognition", "构建人工认知架构",
               "完成ISA Project三层+三控制器, 实现人类级通用认知",
               Priority.HIGH, ["认知", "架构", "ISA", "Agent", "智能"])
        gl.add("complete-gate5", "完成FATA关5(世界建模)",
               "基于已验证的全栈数据流, 构建跨Agent共享世界模型",
               Priority.MID, ["FATA", "关5", "世界", "模型", "认知", "共享"])
        gl.add("verify-pipeline", "验证全栈数据闭环",
               "Dreaming→Brain→Δ胶囊→Arbiter 全栈真实数据闭环验证",
               Priority.LOW, ["验证", "Dreaming", "闭环", "数据"])
        print(f"初始化 {len(gl._goals)} 个目标")

    elif cmd == "list":
        s = gl.stats()
        print(f"目标统计: 总计{s['total']} ")
        for g in s["active"]:
            print(f"  [{g['priority']}] {g['title']} ({g['id']})")

    elif cmd == "relevance":
        if len(sys.argv) < 3:
            print("需提供内容")
            return
        results = gl.relevance(sys.argv[2])
        if results:
            for r in results:
                print(f"  {r['goal_id']}: {r['score']} ({', '.join(r['matched_keywords'])})")
        else:
            print("无匹配目标")

    elif cmd == "should_deep":
        if len(sys.argv) < 3:
            print("需提供内容")
            return
        print(gl.should_deep_process(sys.argv[2]))


if __name__ == "__main__":
    cli()
