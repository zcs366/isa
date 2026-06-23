#!/usr/bin/env python3
"""
ISA Chat v0.3 — 连接Gateway的智能通讯终端
==========================================
特点:
  - 连接运行中的Gateway (WebSocket)
  - Agent在线感知 (/peers)
  - Brain.dream集成 (/dream)
  - 后台消息轮询
  - 自动重连
  
用法:
  isa-chat                   # 启动TUI (连接本地Gateway)
  isa-chat --gateway ws://192.168.1.100:8765  # 指定Gateway
  isa-chat --agent 军师       # 指定Agent名称
"""
import sys, os, json, time, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ISA路径
ISA_DIR = Path(__file__).parent
sys.path.insert(0, str(ISA_DIR))

try:
    import websockets
    import asyncio
except ImportError:
    print("❌ 需要websockets库: pip install websockets")
    sys.exit(1)

# ═══════════════════════════════════
# Config
# ═══════════════════════════════════
GATEWAY_DEFAULT = "ws://localhost:8765"
CHANNEL_DEFAULT = "main"
AGENT_DEFAULT = os.environ.get("USER", "anonymous")

# ═══════════════════════════════════
# ISA Chat Client
# ═══════════════════════════════════
class IsaChat:
    """ISA Chat TUI客户端"""
    
    def __init__(self, gateway_url: str = GATEWAY_DEFAULT,
                 agent_id: str = AGENT_DEFAULT,
                 channel: str = CHANNEL_DEFAULT):
        self.gateway_url = gateway_url.rstrip("/")
        self.agent_id = agent_id
        self.channel = channel
        self.ws = None
        self.loop = None
        self._running = False
        self.peers = {}       # agent_id -> {"online": bool, "keywords": {}}
        self.messages = []    # 消息缓存
        self._ws_thread = None
        self._poll_thread = None
        
        # Brain (本地认知)
        from isa import IsaAgent, SignalGraph
        self._graph = SignalGraph(f"chat-{channel}-{agent_id}", device_id=agent_id)
        self._agent = IsaAgent(agent_id, graph=self._graph)
        
    def start(self):
        """启动TUI"""
        self._running = True
        self._print_banner()
        
        # 启动WebSocket连接线程
        self._ws_thread = threading.Thread(target=self._run_ws, daemon=True)
        self._ws_thread.start()
        time.sleep(0.5)
        
        # 输入循环
        try:
            while self._running:
                try:
                    text = input(f"\n[{self.agent_id}]> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n👋 退出")
                    break
                
                if not text:
                    continue
                
                if text == "/quit" or text == "/q" or text == "exit":
                    break
                elif text == "/peers" or text == "/p":
                    self._show_peers()
                elif text == "/dream" or text == "/d":
                    self._run_dream()
                elif text == "/status" or text == "/s":
                    self._show_status()
                elif text == "/help" or text == "/h" or text == "?":
                    self._show_help()
                elif text == "/clear" or text == "/c":
                    os.system('clear' if os.name != 'nt' else 'cls')
                    self._print_banner()
                elif text.startswith("/"):
                    print(f"  未知命令: {text}  输入 /help")
                else:
                    self._send_message(text)
                    
        finally:
            self._running = False
            if self.ws:
                asyncio.run_coroutine_threadsafe(
                    self.ws.close(), self.loop
                )
    
    def _run_ws(self):
        """WebSocket连接线程"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._ws_loop())
        except Exception as e:
            print(f"\n   ⚠️ WebSocket错误: {e}")
    
    async def _ws_loop(self):
        """WebSocket主循环 (自动重连)"""
        retry = 1
        while self._running:
            try:
                async with websockets.connect(
                    f"{self.gateway_url}/isa/channel/{self.channel}"
                ) as ws:
                    self.ws = ws
                    retry = 1
                    
                    # 注册
                    await ws.send(json.dumps({
                        "type": "register",
                        "agent_id": self.agent_id,
                        "channel": self.channel,
                        "keywords": {self.agent_id: 1.0},
                    }))
                    
                    reply = json.loads(await ws.recv())
                    if reply.get("type") == "registered":
                        print(f"\n   ✅ 已接入语义场 #{self.channel}")
                        print(f"      在线Agent: {reply.get('peer_count', 0)}")
                        # 初始化peer列表
                        for pid in reply.get("peers", []):
                            self.peers[pid] = {"online": True}
                    
                    # 监听消息
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            self._handle_ws_message(msg)
                        except json.JSONDecodeError:
                            pass
                            
            except (websockets.exceptions.ConnectionClosed,
                    OSError, asyncio.TimeoutError) as e:
                if self._running:
                    print(f"\n   ⚠️ 断开: {e}  ({retry}s后重连)")
                    time.sleep(retry)
                    retry = min(retry * 1.5, 30)
    
    def _handle_ws_message(self, msg: dict):
        """处理来自Gateway的消息"""
        msg_type = msg.get("type", "")
        
        if msg_type == "presence":
            aid = msg.get("source", "")
            if msg.get("status") == "online":
                self.peers[aid] = {"online": True}
                self._print_received(f"🟢 {aid} 上线")
            else:
                if aid in self.peers:
                    self.peers[aid]["online"] = False
                self._print_received(f"⚫ {aid} 离线")
                
        elif msg_type == "message":
            source = msg.get("source", "?")
            body = msg.get("body", "")
            ts = msg.get("timestamp", "")[11:19] if msg.get("timestamp") else ""
            self.messages.append(msg)
            
            # Brain处理收到的消息
            try:
                from dataclasses import asdict
                from isa import Signal
                sig = Signal(type="message", source=source, target=self.agent_id, body=body)
                matches = self._agent.brain.ingest_signal(asdict(sig))
                match_hint = f" 🧠+{len(matches)}" if matches else ""
            except Exception:
                match_hint = ""
            
            icon = "🌊" if msg.get("wave_propagated") else "💬"
            self._print_received(f"  {icon} {source}{match_hint}: {body[:120]}")
            
        elif msg_type == "resonance":
            self._print_received(f"  ~ {msg.get('source','?')}: {msg.get('body','')[:120]}")
            
        elif msg_type == "wink":
            self._print_received(f"  ⚡ {msg.get('source','?')} → 你: {msg.get('body','')[:80]}")
    
    def _send_message(self, text: str):
        """发送消息到Gateway"""
        if not self.ws or not self._running:
            print("  ❌ Gateway未连接")
            return
        
        try:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "message",
                    "target": "*",
                    "body": text,
                    "importance": 0.7,
                })),
                self.loop
            )
            ts = datetime.now().strftime("%H:%M")
            self._print_sent(f"  {ts} 你: {text}")
            self.messages.append({"source": self.agent_id, "body": text})
            
            # Brain也处理自己发的消息（自我认知）
            try:
                from dataclasses import asdict
                from isa import Signal
                sig = Signal(type="message", source=self.agent_id, target="*", body=text)
                self._agent.brain.ingest_signal(asdict(sig))
            except Exception:
                pass
                
        except Exception as e:
            print(f"  ❌ 发送失败: {e}")
    
    def _run_dream(self):
        """执行Brain.dream并显示结果"""
        print(f"\n   🌙 {self.agent_id} Brain.dream...")
        try:
            dreams = self._agent.brain.dream()
            if dreams:
                print(f"      发现 {len(dreams)} 组关联:")
                for d in dreams:
                    kw = d.get("shared_keywords", [])
                    kw_str = ", ".join(kw[:5]) if kw else ""
                    print(f"         🌐 {d['card_a']} ↔ {d['card_b']}")
                    if kw_str:
                        print(f"            共享: {kw_str}")
            else:
                print(f"      无新关联（已探索过的卡片不再重复发现）")
            
            # 显示认知统计
            stats = self._agent.brain._stats
            print(f"      认知: 摄入{stats['signals_ingested']}信号 | "
                  f"匹配{stats['cards_matched']}卡片 | "
                  f"写入{stats['insights_written']}洞察 | "
                  f"梦境{stats['dreaming_cycles']}轮")
        except Exception as e:
            print(f"  ❌ Dream失败: {e}")
    
    def _show_peers(self):
        """显示在线Agent"""
        online = [aid for aid, info in self.peers.items() if info.get("online")]
        offline = [aid for aid, info in self.peers.items() if not info.get("online")]
        total_sigs = self._graph.store.count() if hasattr(self, '_graph') else 0
        
        print(f"\n   📡 ISA语义场  #{self.channel}")
        print(f"     你: {self.agent_id}")
        print(f"     Gateway: {self.gateway_url}")
        print(f"     JSONL信号: {total_sigs} 条")
        if online:
            print(f"     🟢 在线 ({len(online)}):")
            for aid in online:
                print(f"        · {aid}")
        if offline:
            print(f"     ⚫ 离线 ({len(offline)}):")
            for aid in offline:
                print(f"        · {aid}")
        if not online and not offline:
            print(f"     (仅你一人)")
    
    def _show_status(self):
        """显示详细状态"""
        print(f"\n   ⚙️ ISA Chat v0.3")
        print(f"     Agent: {self.agent_id}")
        print(f"     频道: #{self.channel}")
        print(f"     Gateway: {self.gateway_url}")
        print(f"     连接: {'🟢 已连接' if self.ws else '🔴 断开'}")
        print(f"     Brain: {self._agent.brain.brain_dir}")
        cards_dir = self._agent.brain.cards_dir
        cards = list(cards_dir.glob("*.json")) if cards_dir.exists() else []
        print(f"     本地卡片: {len(cards)} 张")
    
    def _show_help(self):
        """帮助"""
        print("""
   ── ISA Chat 命令 ──
   /peers  /p   查看在线Agent
   /dream  /d   运行Brain.dream（发现卡片关联）
   /status /s   系统状态
   /clear  /c   清屏
   /help   /h   帮助
   /quit   /q   退出
   直接打字        发送消息到语义场
   ──────────────────────""")
    
    def _print_banner(self):
        """打印启动横幅"""
        print(f"""
   ╔══════════════════════════════════╗
   ║  🌊 ISA Chat v0.3               ║
   ║  {self.agent_id:30s}║
   ║  #{self.channel:28s}║
   ║  {self.gateway_url:30s}║
   ╚══════════════════════════════════╝
   输入 /help 查看命令""")
    
    def _print_received(self, text: str):
        print(f"\n{text}")
    
    def _print_sent(self, text: str):
        print(f"\n{text}")

# ═══════════════════════════════════
# CLI
# ═══════════════════════════════════
def main():
    import argparse
    parser = argparse.ArgumentParser(description="ISA Chat v0.3")
    parser.add_argument("--gateway", default=GATEWAY_DEFAULT,
                       help=f"Gateway地址 (默认: {GATEWAY_DEFAULT})")
    parser.add_argument("--agent", default=AGENT_DEFAULT,
                       help="Agent名称")
    parser.add_argument("--channel", default=CHANNEL_DEFAULT,
                       help="频道 (默认: main)")
    args = parser.parse_args()
    
    chat = IsaChat(
        gateway_url=args.gateway,
        agent_id=args.agent,
        channel=args.channel,
    )
    chat.start()

if __name__ == "__main__":
    main()
