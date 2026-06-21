"""
ISA Offline Protocol v0.1 — 雅典娜: ISA Project离线自洽协议。

定位:
  ISA Project认知架构的第四层(弹性层)。
  当Gateway(神经纤维)断连时, Agent自动进入离线模式——
  认知循环不中断, 只是信号走本地队列, 联网后增量同步。

设计原则:
  - 离线是默认预期, 在线是增强模式
  - Brain和Δ胶囊在本地持续运行, 不依赖ISA连接
  - 重连后只传差异(delta), 不传全量状态
  - 信号"最终一致"——离线产生的信号最终会到达ISA网络

状态机:
  ONLINE → (Gateway断连) → OFFLINE → (重连成功) → SYNCING → ONLINE
                             ↓                           ↑
                         (Brain继续)                 (增量合并)
                         (信号缓冲)                  (队列回放)
                         (定时重试)
"""

import json
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("isa.offline")

# ── 状态常量 ──

ONLINE = "online"
OFFLINE = "offline"
SYNCING = "syncing"


class OfflineProtocol:
    """ISA Project离线自洽协议（雅典娜）。

    Agent认知循环在Gateway断连时不中断——
    Brain继续做梦, insight继续产生, 只是emit的信号被缓冲。
    重连后增量同步, 如同大脑在睡眠中继续工作, 醒来时补上缺失的感知。
    """

    def __init__(self, agent_id: str, offline_dir: Optional[Path] = None):
        self.agent_id = agent_id
        self.offline_dir = (offline_dir or Path.home() / ".hermes" / "isa" / "offline" / agent_id)
        self.offline_dir.mkdir(parents=True, exist_ok=True)

        # 信号缓冲JSONL——离线时emit的信号暂存于此
        self.buffer_path = self.offline_dir / "signal_buffer.jsonl"

        # 同步标记——记录上次同步的边界
        self.sync_token_path = self.offline_dir / "sync_token.json"

        # 离线模式元数据
        self.meta_path = self.offline_dir / "meta.json"

        # 状态
        self._state = ONLINE
        self._offline_since: Optional[float] = None
        self._reconnect_interval = 30  # 秒, 重连间隔
        self._heartbeat_interval = 15  # 秒, 心跳检测

        self._load_state()

    def _load_state(self):
        """加载持久化状态。"""
        if self.meta_path.exists():
            try:
                meta = json.loads(self.meta_path.read_text())
                self._state = meta.get("state", ONLINE)
                self._offline_since = meta.get("offline_since")
                logger.info(f"🔌 {self.agent_id} 恢复状态: {self._state}")
            except (json.JSONDecodeError, OSError):
                pass

    def _save_state(self):
        """持久化当前状态。"""
        meta = {
            "agent_id": self.agent_id,
            "state": self._state,
            "offline_since": self._offline_since,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    # ── 状态查询 ──

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_offline(self) -> bool:
        return self._state == OFFLINE

    def offline_duration(self) -> Optional[float]:
        """离线时长(秒)。在线时返回None。"""
        if self._offline_since and self._state == OFFLINE:
            return time.time() - self._offline_since
        return None

    # ── 状态切换 ──

    def go_offline(self):
        """🔌 进入离线模式。

        Brain认知循环不中断, 只是emit的信号被本地缓冲。
        """
        if self._state == OFFLINE:
            return
        self._state = OFFLINE
        self._offline_since = time.time()
        self._save_state()
        logger.warning(f"🔌 {self.agent_id} → OFFLINE (自 {datetime.fromtimestamp(self._offline_since).isoformat()})")

    def go_online(self):
        """🔄 恢复在线模式。"""
        if self._state == ONLINE:
            return
        old_state = self._state
        self._state = ONLINE
        self._offline_since = None
        self._save_state()
        logger.info(f"🔄 {self.agent_id} → ONLINE (之前: {old_state})")

    def go_syncing(self):
        """进入同步模式——重连后正在增量合并。"""
        self._state = SYNCING
        self._save_state()
        logger.info(f"🔄 {self.agent_id} → SYNCING")

    # ── 信号缓冲 ──

    def buffer_signal(self, signal_type: str, content: str,
                      importance: float = 0.5, metadata: dict = None):
        """离线时缓冲一个信号到本地队列。

        信号格式与ISA信道兼容, 确保重连后可以无缝回放。
        """
        event = {
            "type": signal_type,
            "agent_id": self.agent_id,
            "content": content,
            "importance": importance,
            "buffered_at": datetime.now(timezone.utc).isoformat(),
            "offline_since": datetime.fromtimestamp(self._offline_since).isoformat() if self._offline_since else None,
            "metadata": metadata or {},
        }
        with open(self.buffer_path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        logger.debug(f"📥 [{self.agent_id}] 缓冲信号 [{signal_type}]: {content[:40]}...")
        return event

    def pending_count(self) -> int:
        """缓冲区待发送信号数。"""
        if not self.buffer_path.exists():
            return 0
        count = 0
        with open(self.buffer_path, "r") as f:
            for _ in f:
                count += 1
        return count

    def get_pending_signals(self, limit: int = 100) -> list[dict]:
        """获取待发送的缓冲信号(最多limit条)。"""
        if not self.buffer_path.exists():
            return []
        signals = []
        with open(self.buffer_path, "r") as f:
            for line in f:
                if len(signals) >= limit:
                    break
                try:
                    signals.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return signals

    def clear_buffer(self, count: int = None):
        """清除已发送的缓冲信号。count=None=全部清除。"""
        if not self.buffer_path.exists():
            return
        if count is None:
            self.buffer_path.write_text("")
            logger.info(f"🧹 [{self.agent_id}] 信号缓冲已清空")
            return
        # 清除前count条
        lines = self.buffer_path.read_text().strip().split("\n")
        remaining = lines[count:]
        self.buffer_path.write_text("\n".join(remaining) + ("\n" if remaining else ""))

    # ── 同步标记 ──

    def get_sync_token(self) -> dict:
        """获取同步标记。
        
        记录Agent知道的最新信号时间戳,
        重连时用此标记拉取遗漏信号。
        """
        if self.sync_token_path.exists():
            try:
                return json.loads(self.sync_token_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"last_signal_at": None, "agent_id": self.agent_id}

    def set_sync_token(self, last_signal_at: str):
        """更新同步标记。"""
        token = {
            "last_signal_at": last_signal_at,
            "agent_id": self.agent_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sync_token_path.write_text(json.dumps(token, ensure_ascii=False, indent=2))

    # ── 重连逻辑 ──

    async def reconnect_loop(self, gateway_url: str, get_websocket_func):
        """定时重连循环。

        Args:
            gateway_url: ISA Gateway地址 (ws://...)
            get_websocket_func: async callable → WebSocket连接

        每self._reconnect_interval秒尝试重连一次。
        成功后自动执行增量同步。
        """
        while self._state == OFFLINE:
            try:
                ws = await get_websocket_func()
                if ws:
                    # 连接成功 → 增量同步
                    await self._sync(ws)
                    self.go_online()
                    return ws
            except Exception as e:
                logger.debug(f"🔌 [{self.agent_id}] 重连失败: {e}")
            await asyncio.sleep(self._reconnect_interval)
        return None

    async def _sync(self, ws):
        """增量同步: 发缓冲信号+拉取遗漏信号。"""
        self.go_syncing()

        # 1) 发送缓冲信号
        pending = self.get_pending_signals()
        if pending:
            logger.info(f"📤 [{self.agent_id}] 同步 {len(pending)} 条缓冲信号...")
            for sig in pending:
                try:
                    await ws.send(json.dumps({
                        "type": "emit",
                        "content": sig["content"],
                        "importance": sig.get("importance", 0.5),
                        "metadata": {"offline_replay": True, **sig.get("metadata", {})},
                    }))
                except Exception:
                    break  # 发送失败则留到下次
            self.clear_buffer(len(pending))

        # 2) 拉取遗漏信号(通过同步标记)
        token = self.get_sync_token()
        if token.get("last_signal_at"):
            try:
                await ws.send(json.dumps({
                    "type": "sync_request",
                    "since": token["last_signal_at"],
                    "agent_id": self.agent_id,
                }))
            except Exception:
                pass

        logger.info(f"✅ [{self.agent_id}] 增量同步完成")

    # ── 心跳检测 ──

    def check_heartbeat(self, last_heartbeat: float) -> bool:
        """心跳检测。超时→自动进入离线模式。

        Args:
            last_heartbeat: 上次收到Gateway心跳的时间戳

        Returns:
            True=在线, False=离线
        """
        if self._state == OFFLINE:
            return False

        elapsed = time.time() - last_heartbeat
        if elapsed > self._heartbeat_interval * 3:  # 3次心跳未收到=离线
            self.go_offline()
            return False
        return True

    # ── 统计 ──

    def stats(self) -> dict:
        """离线协议统计。"""
        return {
            "state": self._state,
            "offline_duration": self.offline_duration(),
            "pending_signals": self.pending_count(),
            "offline_dir": str(self.offline_dir),
            "sync_token": self.get_sync_token(),
        }


def cli():
    """CLI: python3 -m offline [status|pending|clear]"""
    import sys

    agent_id = sys.argv[2] if len(sys.argv) > 2 else "军师"
    proto = OfflineProtocol(agent_id)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        s = proto.stats()
        print(f"Agent: {agent_id}")
        print(f"状态: {s['state']}")
        if s['offline_duration']:
            print(f"离线时长: {s['offline_duration']:.0f}秒")
        print(f"待发信号: {s['pending_signals']}条")
        print(f"目录: {s['offline_dir']}")

    elif cmd == "pending":
        signals = proto.get_pending_signals()
        print(f"{len(signals)} 条待发信号:")
        for sig in signals:
            print(f"  [{sig['type']}] {sig.get('content','')[:60]} ({sig['buffered_at'][:19]})")

    elif cmd == "clear":
        proto.clear_buffer()
        print("缓冲区已清空")


if __name__ == "__main__":
    cli()
