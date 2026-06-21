#!/usr/bin/env python3
"""
ISA v0.6.0 — 不可变频道 + 波扩散
================================
v0.5.0 → v0.6.0: 七魂合议驱动的架构翻转

核心变更：
- 信号存储：SQLite INSERT OR REPLACE → JSONL追加（永不覆盖）
- 并发安全：flock（阿瑞斯）
- 时间线叙事：JSONL天然事件流（阿佛洛狄忒）
- 多设备：按device_id分子目录（赫淮斯托斯）
- 分身：isa branch --fork（雅典娜）
- FTS5：从JSONL重建索引（保留检索速度）
- 不可变：发生过的不能被抹去（阿波罗）

不变：
- WaveEngine波扩散引擎
- emit/reflect/send/wink原语
- 结构化骰子评分
- Jaccard语义距离
"""

import argparse
import fcntl
import json
import math
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

ISA_VERSION = "0.6.0"
ISA_HOME = Path.home() / ".hermes" / "isa"
ISA_HOME.mkdir(parents=True, exist_ok=True)

# 频道根目录（阿佛洛狄忒：时间线叙事容器）
CHANNELS_DIR = ISA_HOME / "channels"
CHANNELS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CHANNEL = "main"
DEFAULT_DEVICE_ID = os.environ.get("ISA_DEVICE_ID", "local")

# 波扩散参数
DEFAULT_WAVE_RADIUS = 0.5
DEFAULT_WAVE_DECAY = 0.7
DEFAULT_WAVE_MAX_HOPS = 3
DEFAULT_WAVE_MIN_SCORE = 0.1

# ═══════════════════════════════════════════════════════════════
# 关键词提取（零依赖，纯Python）
# ═══════════════════════════════════════════════════════════════

_STOP_WORDS = set("""
的了吗呢吧啊呀哈嘛哦哪嗯嘿
在是和有这不也那就都还只从把被让给对向
与及及其以及或并而但若虽则因所以因此于是然后
可以能够应该需要已经曾经正在将要即将
一个一种这个那个这些那些每个所有各个
上中下前后来去到进出回过
大大大小高多多少全半
""".split())

_CJK_RE = re.compile(r'[\u4e00-\u9fff]{2,}')
# 使用普通字符串(非raw)避免Python 3.12+的SyntaxWarning
_PUNCT_RE = re.compile('[，。！？；：、""''【】《》（）…—\\s]+')


def extract_keywords(text: str, top_k: int = 10) -> list[str]:
    clean = _PUNCT_RE.sub(' ', text)
    words = _CJK_RE.findall(clean)
    words = [w for w in words if w not in _STOP_WORDS]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(top_k)]


# ═══════════════════════════════════════════════════════════════
# 信号模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class Signal:
    """ISA信号——通信的基本原子。

    v0.6.0新增：device_id（哪个设备写入的）、channel（属于哪个频道）。
    这些字段让JSONL行自带溯源能力——不需要数据库外键。
    """
    type: str          # "message" | "wink" | "resonance" | "presence" | "wave"
    source: str        # 发送者Agent ID
    target: str = "*"
    body: str = ""
    id: str = ""
    timestamp: str = ""
    device_id: str = ""   # v0.6.0新增
    channel: str = ""     # v0.6.0新增
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"s-{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.device_id:
            self.device_id = DEFAULT_DEVICE_ID

    def to_json_line(self) -> str:
        """序列化为JSONL一行。不可变——追加后永不修改。"""
        d = asdict(self)
        # 时间戳用浮点epoch秒（方便merge排序），保留ISO字符串
        d["_ts"] = datetime.fromisoformat(
            self.timestamp.replace('Z', '+00:00')
        ).timestamp()
        return json.dumps(d, ensure_ascii=False) + "\n"

    @staticmethod
    def from_json_line(line: str) -> "Signal":
        d = json.loads(line)
        # 兼容旧格式（无device_id/channel字段）
        if "device_id" not in d:
            d["device_id"] = DEFAULT_DEVICE_ID
        if "channel" not in d:
            d["channel"] = DEFAULT_CHANNEL
        # _ts是内部字段，不传给Signal构造器
        d.pop("_ts", None)
        return Signal(**d)

    @staticmethod
    def extract_timestamp(line: str) -> float:
        """从JSONL行快速提取时间戳（不完整解析）"""
        d = json.loads(line)
        return d.get("_ts", 0.0)


# ═══════════════════════════════════════════════════════════════
# 结构化骰子评分（零LLM，零embedding）
# ═══════════════════════════════════════════════════════════════

def _score_signal(body: str, created_at: float, idx: int = 0, total: int = 1,
                  importance: float = 0.5) -> float:
    L = 2.0 if len(body) >= 60 else (-2.0 if len(body) <= 10 else 0.0)
    P = sum(3 if c in '!！' else 2 if c in '?？' else 0 for c in body)
    R = (idx / max(total, 1)) * 1.5
    age_hours = (time.time() - created_at) / 3600
    T = max(0.1, 1.0 / (1.0 + age_hours / 24.0))
    I = importance * 2.0
    return (L + P + R + I) * T


# ═══════════════════════════════════════════════════════════════
# 语义坐标
# ═══════════════════════════════════════════════════════════════

@dataclass
class SemanticPosition:
    agent_id: str
    keywords: dict[str, float] = field(default_factory=dict)
    last_updated: float = 0.0


def compute_semantic_distance(pos_a: SemanticPosition, pos_b: SemanticPosition) -> float:
    keys_a = set(pos_a.keywords.keys())
    keys_b = set(pos_b.keywords.keys())
    if not keys_a or not keys_b:
        return 1.0
    intersection = keys_a & keys_b
    union = keys_a | keys_b
    if not union:
        return 1.0
    return 1.0 - len(intersection) / len(union)


# ═══════════════════════════════════════════════════════════════
# 频道存储（v0.6.0核心——JSONL追加 + flock + 按设备分目）
# ═══════════════════════════════════════════════════════════════

class ChannelStore:
    """频道的JSONL存储引擎。

    目录结构（赫淮斯托斯）：
      channels/<channel_name>/
        <device_id_1>/
          events.jsonl     ← 本设备写入的不可变事件流
          events.fts5.db   ← FTS5索引（从JSONL重建）
        <device_id_2>/
          events.jsonl
          events.fts5.db
        merged/               ← merge后的事件流（按时间戳排序）
          merged.jsonl
          merged.fts5.db
    """

    def __init__(self, channel: str = DEFAULT_CHANNEL,
                 device_id: str = DEFAULT_DEVICE_ID):
        self.channel = channel
        self.device_id = device_id
        self.device_dir = CHANNELS_DIR / channel / device_id
        self.device_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.device_dir / "events.jsonl"
        self.fts5_path = self.device_dir / "events.fts5.db"
        self._write_lock = threading.Lock()

    def append(self, signal: Signal) -> str:
        """追加一条信号到JSONL（阿波罗：不可抹去）。

        写入流程：
        1. 获取文件锁（阿瑞斯：防并发写损坏）
        2. 序列化为JSONL一行
        3. 追加写入
        4. 释放锁

        JSONL末尾无换行也能正确追加（自动补换行）。
        """
        signal.device_id = self.device_id
        signal.channel = self.channel

        line = signal.to_json_line()
        with self._write_lock:
            with open(self.events_path, "ab") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    # 以二进制追加模式写入：0次seek，0次read
                    # 这是抵御多字节UTF-8字符在并发seek+read时导致
                    # UnicodeDecodeError 的唯一方式
                    # 新文件直接写；已有文件自动追加到末尾
                    f.write(line.encode("utf-8"))
                    f.flush()
                    os.fsync(f.fileno())  # 确保写入磁盘（不可变的基础）
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        return signal.id

    def read_all(self, limit: int = None) -> list[Signal]:
        """读取所有事件（按写入顺序——即时间顺序）"""
        if not self.events_path.exists():
            return []

        signals = []
        with open(self.events_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                signals.append(Signal.from_json_line(line))
                if limit and len(signals) >= limit:
                    break
        return signals

    def read_range(self, start_ts: float = None, end_ts: float = None) -> list[Signal]:
        """按时间范围读取（--fork的底层操作）"""
        if not self.events_path.exists():
            return []

        signals = []
        with open(self.events_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ts = Signal.extract_timestamp(line)
                if start_ts and ts < start_ts:
                    continue
                if end_ts and ts > end_ts:
                    continue
                signals.append(Signal.from_json_line(line))
        return signals

    def merge_devices(self) -> "ChannelStore":
        """合并所有设备的JSONL，按时间戳排序。（赫淮斯托斯）

        排序键: (_ts, device_id) — device_id作为次要键防止同一微秒
        内不同设备的事件的因果倒置。
        
        注意: 本方法使用 wall-clock 时间戳，依赖 NTP 或等效时钟同步。
        在 VM 回滚、WSL 休眠、或时钟大幅偏差场景下，排序可能不正确。
        未来版本应用混合逻辑时钟(HLC)替代 wall-clock 时间戳。
        """
        merged_dir = CHANNELS_DIR / self.channel / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)
        merged_path = merged_dir / "events.jsonl"

        all_events = []

        # 收集所有设备的事件
        channel_dir = CHANNELS_DIR / self.channel
        for device_dir in channel_dir.iterdir():
            if not device_dir.is_dir() or device_dir.name == "merged":
                continue
            events_file = device_dir / "events.jsonl"
            if not events_file.exists():
                continue
            device_name = device_dir.name
            with open(events_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_events.append((line, device_name))

        # 按(时间戳, device_id)排序——防止同微秒因果倒置
        all_events.sort(key=lambda x: (Signal.extract_timestamp(x[0]), x[1]))

        # 写入合并文件（flock保护，防止并发写入merged目录）
        with open(merged_path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                for line, _ in all_events:
                    f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        # 返回只读merged store（MRO防止误写入——赫淮斯托斯P0修复）
        return ChannelStore(self.channel, "merged")

    def count(self) -> int:
        if not self.events_path.exists():
            return 0
        count = 0
        with open(self.events_path, "r") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count


# ═══════════════════════════════════════════════════════════════
# FTS5索引（从JSONL重建，保留检索速度）
# ═══════════════════════════════════════════════════════════════

class FTS5Index:
    """FTS5全文索引——从JSONL事件流重建，不依赖SQLite主存储。

    为什么还需要SQLite？FTS5是SQLite的原生功能。
    但这里的SQLite只存索引，不存数据。数据永在JSONL。
    索引可以随时从JSONL重建——丢了也不怕。
    """

    def __init__(self, store: ChannelStore):
        self.store = store
        self.db_path = store.fts5_path
        self._lock = threading.Lock()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fts_index (
                    signal_id TEXT PRIMARY KEY,
                    body TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fts_type ON fts_index(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fts_source ON fts_index(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fts_target ON fts_index(target)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fts_time ON fts_index(created_at)")
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_content
                USING fts5(body, content=fts_index, content_rowid=rowid)
            """)
            conn.commit()
            conn.close()

    def rebuild(self):
        """从JSONL完全重建FTS5索引。

        这是"索引丢了不可惜"的底气——JSONL在，索引就能重生。
        """
        self._init_db()

        signals = self.store.read_all()
        if not signals:
            return

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))

            # 清空旧索引
            conn.execute("DELETE FROM fts_index")

            for i, sig in enumerate(signals):
                score = _score_signal(sig.body, time.time(), i, len(signals),
                                     importance=sig.meta.get("importance", 0.5))
                ts = datetime.fromisoformat(
                    sig.timestamp.replace('Z', '+00:00')
                ).timestamp()
                conn.execute(
                    "INSERT OR REPLACE INTO fts_index VALUES (?,?,?,?,?,?,?)",
                    (sig.id, sig.body, sig.type, sig.source, sig.target, score, ts)
                )

            conn.commit()
            # 重建FTS5全文索引
            conn.execute("INSERT INTO fts_content(fts_content) VALUES('rebuild')")
            conn.commit()
            conn.close()

    def search(self, query: str = None, source: str = None,
               target: str = None, signal_type: str = None,
               limit: int = 20) -> list[str]:
        """检索，返回匹配的信号ID列表。调用方根据ID从JSONL取完整Signal。"""
        if not self.db_path.exists():
            return []

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))

            if query:
                has_cjk = bool(re.search(r'[\u4e00-\u9fff]', query))
                if has_cjk:
                    conditions = ["1=1"]
                    params = []
                    for term in query.split():
                        if term.strip():
                            conditions.append("body LIKE ?")
                            params.append(f"%{term.strip()}%")
                    where = " AND ".join(conditions)
                    rows = conn.execute(
                        f"SELECT signal_id FROM fts_index WHERE {where} "
                        f"ORDER BY score DESC, created_at DESC LIMIT ?",
                        params + [limit]
                    ).fetchall()
                else:
                    try:
                        rows = conn.execute("""
                            SELECT i.signal_id FROM fts_content f
                            JOIN fts_index i ON f.rowid = i.rowid
                            WHERE fts_content MATCH ?
                            ORDER BY i.score DESC, i.created_at DESC
                            LIMIT ?
                        """, (query, limit)).fetchall()
                    except sqlite3.OperationalError:
                        rows = []
            else:
                conditions = ["1=1"]
                params = []
                if source:
                    conditions.append("source = ?")
                    params.append(source)
                if target and target != "*":
                    conditions.append("(target = ? OR target = '*')")
                    params.append(target)
                if signal_type:
                    conditions.append("type = ?")
                    params.append(signal_type)
                where = " AND ".join(conditions)
                rows = conn.execute(
                    f"SELECT signal_id FROM fts_index WHERE {where} "
                    f"ORDER BY score DESC, created_at DESC LIMIT ?",
                    params + [limit]
                ).fetchall()

            conn.close()
            return [r[0] for r in rows]

    def active_sources(self, hours: int = 24) -> list[str]:
        if not self.db_path.exists():
            return []
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cutoff = time.time() - hours * 3600
            rows = conn.execute(
                "SELECT DISTINCT source FROM fts_index WHERE created_at > ?",
                (cutoff,)
            ).fetchall()
            conn.close()
            return [r[0] for r in rows]


# ═══════════════════════════════════════════════════════════════
# 信号图谱（v0.6.0——JSONL + FTS5双引擎）
# ═══════════════════════════════════════════════════════════════

class SignalGraph:
    """信号图谱——ISA的核心。

    v0.6.0架构：
      - 存储：ChannelStore（JSONL追加，flock保护）
      - 检索：FTS5Index（从JSONL重建，SQLite仅存索引）
      - 数据永在JSONL。索引可随时重建。
    """

    def __init__(self, channel: str = DEFAULT_CHANNEL,
                 device_id: str = DEFAULT_DEVICE_ID):
        self.channel = channel
        self.device_id = device_id
        self.store = ChannelStore(channel, device_id)
        self.index = FTS5Index(self.store)

    def ingest(self, signal: Signal) -> str:
        """写入信号。不可变追加。

        FTS5索引采用攒批重建策略：每写入N条信号后触发一次全量重建，
        而非每条写入后重建。避免O(N²)的索引维护成本。
        """
        sid = self.store.append(signal)
        # 攒批：只在信号数达到5的倍数时重建索引
        if self.store.count() % 5 == 0:
            self.index.rebuild()
        return sid

    def retrieve(self, *, source: str = None, target: str = None,
                 signal_type: str = None, query: str = None,
                 limit: int = 20) -> list[Signal]:
        """检索信号。先从FTS5索引拿到ID列表，再从JSONL取完整对象。"""
        ids = self.index.search(
            query=query, source=source, target=target,
            signal_type=signal_type, limit=limit
        )

        if not ids:
            return []

        id_set = set(ids)
        results = []
        for sig in self.store.read_all():
            if sig.id in id_set:
                results.append(sig)
                if len(results) >= limit:
                    break
        return results

    def active_sources(self, hours: int = 24) -> list[str]:
        return self.index.active_sources(hours)

    def stats(self) -> dict:
        return {
            "channel": self.channel,
            "device_id": self.device_id,
            "total_signals": self.store.count(),
            "store_path": str(self.store.events_path),
            "index_path": str(self.store.fts5_path),
        }


# ═══════════════════════════════════════════════════════════════
# 波扩散引擎（不变）
# ═══════════════════════════════════════════════════════════════

class WaveEngine:
    def __init__(self, graph: SignalGraph,
                 radius: float = DEFAULT_WAVE_RADIUS,
                 decay: float = DEFAULT_WAVE_DECAY,
                 max_hops: int = DEFAULT_WAVE_MAX_HOPS,
                 min_score: float = DEFAULT_WAVE_MIN_SCORE):
        self.graph = graph
        self.radius = radius
        self.decay = decay
        self.max_hops = max_hops
        self.min_score = min_score

    def get_agent_profile(self, agent_id: str, signal_limit: int = 50) -> SemanticPosition:
        signals = self.graph.retrieve(source=agent_id, limit=signal_limit)
        all_keywords = []
        for sig in signals:
            all_keywords.extend(extract_keywords(sig.body, top_k=5))
        counter = Counter(all_keywords)
        total = sum(counter.values()) or 1
        keywords = {w: c / total for w, c in counter.most_common(20)}
        return SemanticPosition(agent_id=agent_id, keywords=keywords, last_updated=time.time())

    def find_nearby_agents(self, source_profile: SemanticPosition,
                           candidate_agents: list[str]) -> list[tuple[str, float]]:
        nearby = []
        for agent_id in candidate_agents:
            if agent_id == source_profile.agent_id:
                continue
            target_profile = self.get_agent_profile(agent_id)
            dist = compute_semantic_distance(source_profile, target_profile)
            if dist <= self.radius:
                nearby.append((agent_id, dist))
        nearby.sort(key=lambda x: x[1])
        return nearby

    def emit(self, signal: Signal, importance: float = 0.5,
             radius: float = None, max_hops: int = None) -> list[str]:
        r = radius if radius is not None else self.radius
        hops = max_hops if max_hops is not None else self.max_hops
        sig_id = self.graph.ingest(signal)
        if importance < 0.3 or hops <= 0:
            return [sig_id]

        source_profile = self.get_agent_profile(signal.source)
        candidates = self.graph.active_sources(hours=24)
        nearby = self.find_nearby_agents(source_profile, candidates)

        wave_id = f"w-{uuid.uuid4().hex[:8]}"
        propagated_ids = [sig_id]

        for target_agent, dist in nearby:
            decayed_importance = importance * (1.0 - dist)
            if decayed_importance < 0.1:
                continue
            wave_signal = Signal(
                type="wave", source=signal.source, target=target_agent,
                body=signal.body,
                meta={
                    "wave_id": wave_id, "original_id": sig_id,
                    "hop": 1, "max_hops": hops, "decay": self.decay,
                    "importance": round(decayed_importance, 3),
                    "semantic_distance": round(dist, 3),
                    "propagated": True,
                }
            )
            wid = self.graph.ingest(wave_signal)
            propagated_ids.append(wid)

        return propagated_ids

    def reflect(self, incoming_wave: Signal, reflection_body: str,
                importance: float = 0.3) -> list[str]:
        meta = incoming_wave.meta
        hop = meta.get("hop", 1)
        max_hops = meta.get("max_hops", self.max_hops)
        remaining_hops = max_hops - hop
        if remaining_hops <= 0:
            return []

        reflect_signal = Signal(
            type="resonance", source=incoming_wave.target, target="*",
            body=reflection_body,
            meta={
                "reflected_from": incoming_wave.id,
                "original_wave": meta.get("wave_id", ""),
                "hop": hop + 1, "max_hops": max_hops,
                "decay": self.decay * 0.8, "importance": importance,
            }
        )
        return self.emit(reflect_signal, importance=importance * self.decay,
                        max_hops=remaining_hops)


# ═══════════════════════════════════════════════════════════════
# ISA Project认知单元（Agent）
# 每个IsaAgent = ISA Project这个人工大脑中的一个神经元
# ═══════════════════════════════════════════════════════════════

class IsaAgent:
    """ISA Project认知单元（神经元）。

    IsaAgent是ISA Project这个人工认知架构中的基本活性单元。
    每个Agent拥有:
      - ISA Layer连接（Gateway+波扩散）——神经纤维，与其他Agent通信
      - Brain（大脑皮层）——独立的认知处理单元
      - Δ胶囊接口（DreamBridge）——记忆固化管道
    
    Agent不是独立程序——是ISA Project这个人工大脑中的一个神经元。
    
    认知循环:
      receive(信号) → brain.ingest_signal(感知) → brain.dream/predict(思考)
      → brain.insight(决策) → emit(行动) → 信号回到ISA网络
    """
    def __init__(self, agent_id: str, graph: SignalGraph = None,
                 wave_engine: WaveEngine = None, brain = None):
        self.agent_id = agent_id
        self.graph = graph or SignalGraph()
        self.wave = wave_engine or WaveEngine(self.graph)
        self._handlers: list[callable] = []
        self._running = False

        # 🦉雅典娜: 离线自洽协议——Gateway断连时保持认知循环
        from offline import OfflineProtocol as _OP
        self._offline = _OP(agent_id)

        # 🧠 Brain——ISA Project个体认知层（Agent的大脑皮层）
        if brain is None:
            from brain import Brain
            # 📨赫尔墨斯: 新洞察自动触发emit→二次波扩散
            def _emit_insight(card_id, content):
                try:
                    self.emit(f"[Brain]🧠 {card_id}: {content[:80]}", importance=0.6)
                except Exception:
                    pass
            brain = Brain(agent_id, on_new_insight=_emit_insight)
        self.brain = brain

    # ── 基础通信 ──
    def send(self, target: str, body: str, meta: dict = None) -> str:
        sig = Signal(type="message", source=self.agent_id, target=target,
                     body=body, meta=meta or {})
        return self.graph.ingest(sig)

    def wink(self, target: str, signal_name: str = "ping", data: dict = None) -> str:
        sig = Signal(type="wink", source=self.agent_id, target=target,
                     body=signal_name, meta=data or {})
        return self.graph.ingest(sig)

    def resonate(self, content: str, meta: dict = None) -> str:
        sig = Signal(type="resonance", source=self.agent_id, target="resonance",
                     body=content, meta=meta or {})
        return self.graph.ingest(sig)

    def emit(self, body: str, importance: float = 0.5,
             target: str = "*", radius: float = None,
             max_hops: int = None, meta: dict = None) -> list[str]:
        sig = Signal(type="message", source=self.agent_id, target=target,
                     body=body, meta=meta or {})
        sig.meta["importance"] = importance
        return self.wave.emit(sig, importance=importance,
                             radius=radius, max_hops=max_hops)

    def reflect(self, incoming_wave_id: str, reflection_body: str,
                importance: float = 0.3) -> list[str]:
        signals = self.graph.retrieve(query=incoming_wave_id, limit=1)
        if not signals:
            return []
        return self.wave.reflect(signals[0], reflection_body, importance)

    def poll(self, *, signal_type: str = None, limit: int = 20) -> list[Signal]:
        return self.graph.retrieve(target=self.agent_id, signal_type=signal_type, limit=limit)

    def search(self, query: str, limit: int = 20) -> list[Signal]:
        return self.graph.retrieve(query=query, limit=limit)

    def incoming_waves(self, limit: int = 20) -> list[Signal]:
        return self.graph.retrieve(target=self.agent_id, signal_type="wave", limit=limit)

    # ── 分身操作（雅典娜）──
    def branch(self, from_timestamp: str, new_channel: str) -> "IsaAgent":
        """从当前频道在指定时间戳处切出一个新分身频道。

        --fork 的工程实现：
        1. 读取当前频道的所有事件
        2. 截取时间戳之后的事件（分身只复制fork点之后的事件）
        3. 写入新频道的JSONL
        4. 返回新频道的Agent

        分身是一个新的IsaAgent，有自己的频道、自己的事件流。
        它从fork点开始独立演化——不继承fork点之前的历史。
        （如需fork点之前上下文，从母频道merge_devices获取。）
        """
        fork_ts = datetime.fromisoformat(from_timestamp).timestamp()

        # 读取fork点之后的事件
        events = self.graph.store.read_range(start_ts=fork_ts)

        # 创建新频道
        new_store = ChannelStore(new_channel, self.graph.device_id)
        new_graph = SignalGraph(new_channel, self.graph.device_id)

        # 写入fork点之后的事件到新频道
        for sig in events:
            sig.channel = new_channel
            new_graph.ingest(sig)

        new_graph.index.rebuild()
        print(f"[ISA] 分身已创建: channel={new_channel}, "
              f"from={from_timestamp}, events={len(events)}")

        return IsaAgent(self.agent_id, new_graph, WaveEngine(new_graph))

    # ── 工具 ──
    def peers(self) -> list[str]:
        return self.graph.active_sources(hours=1)

    def profile(self) -> SemanticPosition:
        return self.wave.get_agent_profile(self.agent_id)

    def distance_to(self, other_agent: str) -> float:
        my_pos = self.wave.get_agent_profile(self.agent_id)
        other_pos = self.wave.get_agent_profile(other_agent)
        return compute_semantic_distance(my_pos, other_pos)

    def on_signal(self, handler: callable):
        self._handlers.append(handler)

    def listen(self, interval: float = 0.5):
        """本地监听——轮询Core JSONL中的消息（适合纯本地模式）。"""
        self._running = True
        def _loop():
            while self._running:
                signals = self.graph.retrieve(target=self.agent_id, limit=10)
                for sig in signals:
                    for h in self._handlers:
                        try: h(sig)
                        except Exception: pass
                time.sleep(interval)
        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        return thread

    def _fingerprint_path(self) -> Path:
        """语义指纹持久化文件路径。"""
        fp_dir = ISA_HOME / "fingerprints"
        fp_dir.mkdir(parents=True, exist_ok=True)
        return fp_dir / f"{self.agent_id}.json"

    def _load_fingerprint(self) -> dict:
        """加载持久化语义指纹。"""
        path = self._fingerprint_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                print(f"[ISA] 🏛️ 指纹加载: {len(data)}个关键词 from {path}")
                return data
            except Exception as e:
                print(f"[ISA] ⚠ 指纹加载失败: {e}")
        print(f"[ISA] 🏛️ 指纹未找到: {path}")
        return {}

    def _save_fingerprint(self, keywords: dict):
        """保存语义指纹到持久化文件。"""
        path = self._fingerprint_path()
        path.write_text(json.dumps(keywords, ensure_ascii=False, indent=2))

    def agently_listen(self, gateway_url: str = "ws://localhost:8766",
                       keywords: dict = None,
                       outbox_path: str = None):
        """Gateway监听——WebSocket连接Gateway，实时收发，自动重连。

        替代独立的hermes_adapter daemon进程。
        IsaAgent现在是单进程三模式之一：agently_listen = daemon模式。

        Args:
            gateway_url: Gateway WebSocket地址
            keywords: 语义指纹（默认从agent profile提取）
            outbox_path: outbox文件路径（用于接收外部send命令写入的消息）
        """
        import asyncio as _asyncio

        _channel = self.graph.channel
        # 雅典娜赐福: 优先从持久化指纹文件加载，保证语义身份稳定
        _keywords = keywords or self._load_fingerprint() or {}
        if not _keywords:
            # 兜底: 从Core profile提取
            p = self.profile()
            _keywords = p.keywords
        _outbox = Path(outbox_path) if outbox_path else None

        async def _run():
            try:
                import websockets as _ws
            except ImportError:
                print("[ISA] ❌ agently_listen需要: pip install websockets")
                return

            url = f"{gateway_url}/isa/channel/{_channel}"
            delay = 3

            while True:
                try:
                    print(f"[ISA] 🔌 {self.agent_id} 连接Gateway: {url}")
                    async with _ws.connect(url, ping_interval=20, ping_timeout=10, close_timeout=5) as ws:
                        await ws.send(json.dumps({
                            "type": "register",
                            "agent_id": self.agent_id,
                            "channel": _channel,
                            "keywords": _keywords,
                        }, ensure_ascii=False))
                        reply = json.loads(await ws.recv())
                        if reply.get("type") != "registered":
                            print(f"[ISA] ❌ 注册失败: {reply}")
                            await _asyncio.sleep(delay)
                            continue
                        print(f"[ISA] ✅ {self.agent_id} 已连接 · {reply.get('peer_count',0)} Agent在线")
                        # 🦉雅典娜: 离线→在线同步(发缓冲信号)
                        if self._offline.state != "online":
                            self._offline.go_online()
                            _pending = self._offline.pending_count()
                            if _pending > 0:
                                print(f"[ISA] 📤 同步 {_pending} 条离线缓冲信号...")
                        self._offline.set_sync_token(datetime.now(timezone.utc).isoformat())
                        # 雅典娜: 持久化语义指纹
                        if _keywords:
                            self._save_fingerprint(_keywords)
                            print(f"[ISA] 🏛️ 语义指纹已持久化: {len(_keywords)}个关键词")

                        # ☀️⏳ Dreaming引擎: Agent在线后自动启动认知循环
                        # 如果设了ISA_DREAM_LLM环境变量→启动LLM增强Dreaming
                        _dream_llm = os.environ.get("ISA_DREAM_LLM", "")
                        if not _dream_llm:
                            _dream_llm = os.environ.get("ISA_LLM_ENDPOINT", "")
                        try:
                            self.brain.start_dreaming(
                                llm_endpoint=_dream_llm or None,
                                interval=300,  # 5分钟扫描一次
                            )
                        except Exception:
                            pass  # Dreaming启动失败不影响通信

                        # ☀️阿波罗: 初始化目标层(仅首次)
                        try:
                            if not self.brain._goal_initialized:
                                from goal import Priority as _P
                                self.brain.goal.add(
                                    "architect-cognition", "构建人工认知架构",
                                    "完成ISA Project三层+三控制器",
                                    _P.HIGH,
                                    ["认知", "架构", "ISA", "Agent", "智能"])
                                self.brain.goal.add(
                                    "complete-gate5", "完成FATA关5(世界建模)",
                                    "跨Agent共享世界模型",
                                    _P.MID,
                                    ["FATA", "关5", "世界", "模型", "共享"])
                                self.brain._goal_initialized = True
                        except Exception:
                            pass

                        async def _recv():
                            try:
                                async for raw in ws:
                                    msg = json.loads(raw)
                                    sig = Signal(
                                        type=msg.get("type","message"),
                                        source=msg.get("source","?"),
                                        target=msg.get("target","*"),
                                        body=msg.get("body",""),
                                        meta=msg.get("meta",{}),
                                    )
                                    self.graph.ingest(sig)  # 写入本地Core

                                    # 🧠 jika: 信号进入Brain→触发记忆检索
                                    try:
                                        recalled = self.brain.ingest_signal({
                                            "type": msg.get("type","message"),
                                            "source": msg.get("source","?"),
                                            "body": msg.get("body",""),
                                        })
                                        if recalled:
                                            sig.meta["_brain_recall"] = recalled
                                        # ⏳克洛诺斯: 预测
                                        try:
                                            preds = self.brain.predict(msg.get("body",""))
                                            if preds:
                                                sig.meta["_brain_predict"] = preds
                                        except Exception:
                                            pass
                                        # 💎阿佛洛狄忒: 仪式感
                                        try:
                                            recognition = self.brain.recognize(msg.get("body",""))
                                            if recognition:
                                                sig.meta["_brain_recognize"] = recognition
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass  # Brain异常不阻断通信

                                    for h in self._handlers:
                                        try: h(sig)
                                        except Exception: pass
                            except Exception:
                                pass

                        async def _send_outbox():
                            if not _outbox:
                                while True:
                                    await _asyncio.sleep(1)
                            last_pos = 0
                            try:
                                while True:
                                    await _asyncio.sleep(0.5)
                                    if _outbox.exists():
                                        with open(_outbox, "rb") as f:
                                            f.seek(last_pos)
                                            for line in f:
                                                try:
                                                    m = json.loads(line.decode().strip())
                                                    await ws.send(json.dumps(m, ensure_ascii=False))
                                                except Exception:
                                                    pass
                                            last_pos = f.tell()
                            except Exception:
                                pass

                        await _asyncio.gather(_recv(), _send_outbox())
                        delay = 3  # 成功连接后重置退避

                except Exception as e:
                    print(f"[ISA] ⚠ {self.agent_id} 断连: {type(e).__name__}")
                    self._offline.go_offline()  # 🦉进入离线模式
                print(f"[ISA] 🔄 {delay}秒后重连...")
                await _asyncio.sleep(delay)
                delay = min(delay * 1.5, 30)

        # 在新线程中启动asyncio事件循环
        def _thread_run():
            _asyncio.run(_run())
        t = threading.Thread(target=_thread_run, daemon=True)
        t.start()
        return t

    def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"ISA v{ISA_VERSION} — 不可变频道 + 波扩散",
    )
    parser.add_argument("--id", default=None, help="分身ID")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL, help="频道名")
    parser.add_argument("--device", default=DEFAULT_DEVICE_ID, help="设备ID")

    # 基本通信
    parser.add_argument("--send", nargs=2, metavar=("TARGET", "CONTENT"))
    parser.add_argument("--wink", nargs=2, metavar=("TARGET", "SIGNAL"))
    parser.add_argument("--resonate", metavar="CONTENT")
    parser.add_argument("--emit", nargs="+", metavar=("CONTENT", "IMPORTANCE"),
                        help="发射信号+波扩散")
    parser.add_argument("--reflect", nargs=2, metavar=("WAVE_ID", "CONTENT"))
    parser.add_argument("--search", metavar="QUERY")
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--incoming", action="store_true")

    # 分身（雅典娜）
    parser.add_argument("--branch", nargs=2, metavar=("FROM_TS", "NEW_CHANNEL"),
                        help="从指定时间戳切出分身频道 (ISO格式)")

    # 合并（赫淮斯托斯）
    parser.add_argument("--merge", action="store_true",
                        help="合并所有设备的事件流")

    # 索引重建
    parser.add_argument("--reindex", action="store_true",
                        help="从JSONL重建FTS5索引")

    # 工具
    parser.add_argument("--peers", action="store_true")
    parser.add_argument("--distance", metavar="AGENT_ID")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--listen", action="store_true")
    parser.add_argument("--agently-listen", action="store_true",
                        help="Gateway监听模式（WebSocket实时收发+自动重连）")
    parser.add_argument("--gateway", default="ws://localhost:8766",
                        help="Gateway地址（配合--agently-listen使用）")
    parser.add_argument("--keywords-file", default=None,
                        help="语义指纹JSON文件路径（雅典娜赐福）")

    args = parser.parse_args()
    agent_id = args.id or f"isa-{os.getpid()}"
    graph = SignalGraph(args.channel, args.device)
    agent = IsaAgent(agent_id, graph)

    if args.send:
        target, content = args.send
        sid = agent.send(target, content)
        print(f"[ISA] → {target}: {content}")
        print(f"       id: {sid}")

    elif args.wink:
        target, signal_name = args.wink
        sid = agent.wink(target, signal_name)
        print(f"[ISA] ⚡眨眼 → {target}: {signal_name}")

    elif args.resonate:
        sid = agent.resonate(args.resonate)
        print(f"[ISA] ~共振: {args.resonate}")

    elif args.emit:
        content = args.emit[0]
        importance = float(args.emit[1]) if len(args.emit) > 1 else 0.5
        ids = agent.emit(content, importance=importance)
        print(f"[ISA] 🌊 发射 + 波扩散:")
        print(f"       原信号: {ids[0]}")
        print(f"       扩散副本: {len(ids)-1} 个")

    elif args.reflect:
        wave_id, content = args.reflect
        ids = agent.reflect(wave_id, content)
        print(f"[ISA] ↻ 反射: {len(ids)} 扩散副本")

    elif args.branch:
        from_ts, new_channel = args.branch
        agent.branch(from_ts, new_channel)
        print(f"[ISA] 🦉 分身频道创建: {new_channel}")

    elif args.merge:
        merged = graph.store.merge_devices()
        merged.index.rebuild()
        print(f"[ISA] 🔨 合并完成: {merged.store.count()} 事件")
        print(f"       路径: {merged.store.events_path}")

    elif args.reindex:
        graph.index.rebuild()
        print(f"[ISA] 索引重建完成: {graph.store.count()} 事件")

    elif args.search:
        results = agent.search(args.search)
        print(f"[ISA] 搜索 '{args.search}': {len(results)} 条")
        for s in results:
            dev = f" [{s.device_id}]" if s.device_id else ""
            print(f"  [{s.type}]{dev} {s.source} → {s.target}: {s.body[:80]}")

    elif args.poll:
        results = agent.poll()
        print(f"[ISA] {agent_id} 收件箱 ({len(results)}):")
        for s in results:
            prop = "🌊" if s.meta.get("propagated") else " "
            print(f"  {prop}[{s.type}] {s.source}: {s.body[:80]}")

    elif args.incoming:
        waves = agent.incoming_waves()
        print(f"[ISA] 🌊 扩散到达 ({len(waves)}):")
        for s in waves:
            dist = s.meta.get("semantic_distance", "?")
            print(f"  [{s.source} 距离:{dist}] {s.body[:80]}")

    elif args.peers:
        peers = agent.peers()
        print(f"[ISA] 活跃分身 ({len(peers)}):")
        for p in sorted(peers):
            if p != agent_id:
                dist = agent.distance_to(p)
                bar = "█" * max(1, int((1.0 - dist) * 10))
                print(f"  {p}  [{bar}] dist={dist:.2f}")

    elif args.distance:
        dist = agent.distance_to(args.distance)
        print(f"[ISA] 语义距离: {agent_id} ↔ {args.distance} = {dist:.3f}")

    elif args.profile:
        p = agent.profile()
        print(f"[ISA] {agent_id} 的语义位置:")
        items = sorted(p.keywords.items(), key=lambda x: -x[1])[:15]
        for kw, freq in items:
            bar = "█" * int(freq * 50)
            print(f"  {kw:8s} {bar} {freq:.3f}")

    elif args.stats:
        s = graph.stats()
        print(f"[ISA] 频道统计:")
        for k, v in s.items():
            print(f"  {k}: {v}")

    elif args.listen:
        print(f"[ISA] 分身 '{agent_id}' 监听中（频道 {args.channel}，设备 {args.device}）...")
        agent.on_signal(lambda sig: print(
            f"  [{sig.type}] {sig.source}: {sig.body[:80]}"))
        agent.listen()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            agent.stop()
            print("\n[ISA] 退出")

    elif args.agently_listen:
        print(f"[ISA] 分身 '{agent_id}' Gateway监听模式")
        # 雅典娜: 加载显式指纹文件（若指定）
        keywords = {}
        if args.keywords_file:
            try:
                keywords = json.loads(Path(args.keywords_file).read_text())
                print(f"[ISA] 🏛️ 指纹文件加载: {len(keywords)}个关键词")
            except Exception as e:
                print(f"[ISA] ⚠ 指纹文件加载失败: {e}")
        else:
            profile = agent.profile()
            keywords = profile.keywords
        agent.on_signal(lambda sig: print(
            f"  [{sig.type}] {sig.source}: {sig.body[:80]}"))
        agent.agently_listen(
            gateway_url=args.gateway,
            keywords=keywords,
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            agent.stop()
            print("\n[ISA] 退出")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
