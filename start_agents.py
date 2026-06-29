#!/usr/bin/env python3
"""ISA Agent 守护启动器 — 让语义场里有Agent在线"""
import sys, os, json, time, subprocess, threading, signal
from pathlib import Path

ISA_DIR = Path.home() / "projects" / "isa"
GATEWAY_URL = "ws://localhost:8765"
AGENTS = ["军师", "子贡", "包拯"]
PIDS = []

def spawn_agent(name):
    """启动一个Agent进程连上Gateway，保持在在线"""
    script = f"""
import sys, json, asyncio, time
sys.path.insert(0, '{ISA_DIR}')
sys.path.insert(0, '{ISA_DIR}/client')
from isa import IsaAgent, SignalGraph

async def run():
    try:
        import websockets
        async with websockets.connect('{GATEWAY_URL}/isa/channel/main') as ws:
            await ws.send(json.dumps({{
                'type': 'register',
                'agent_id': '{name}',
                'channel': 'main',
                'keywords': {{{agent_kw(name)}}}
            }}))
            reply = json.loads(await ws.recv())
            print(f'[{name}] 接入语义场 ✅ peers={{reply.get("peer_count",0)}}')
            
            # 加载Brain
            graph = SignalGraph("main", device_id='{name}')
            agent = IsaAgent('{name}', graph=graph)
            
            # 保持在线 — 每30秒dream一次
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    msg = json.loads(raw)
                    if msg.get('type') == 'message':
                        body = msg.get('body', '')
                        from dataclasses import asdict
                        from isa import Signal
                        sig = Signal(type='message', source=msg.get('source','?'),
                                     target='{name}', body=body)
                        agent.brain.ingest_signal(asdict(sig))
                        # 回复
                        await ws.send(json.dumps({{
                            'type': 'message', 'target': msg.get('source'),
                            'body': f'[🧠 {name}收到] 已处理: {{body[:60]}}'
                        }}))
                except asyncio.TimeoutError:
                    # 定时dream
                    dreams = agent.brain.dream()
                    if dreams:
                        print(f'[{name}] 🌙 dream: {{len(dreams)}} groups')
    except Exception as e:
        print(f'[{name}] ❌ {{e}}')

asyncio.run(run())
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    PIDS.append(proc)
    return proc

def agent_kw(name):
    kws = {"军师": "'isa':0.9,'认知':0.8,'架构':0.7,'波扩散':0.6",
            "子贡": "'资源':0.9,'调度':0.8,'并发':0.7,'语义':0.6",
            "包拯": "'审计':0.9,'合规':0.8,'验证':0.7,'cap':0.6"}
    return kws.get(name, f"'{name}':1.0")

def main():
    print("🧠 ISA Agent 守护启动...")
    for name in AGENTS:
        proc = spawn_agent(name)
        print(f"   🟢 {name} (PID={proc.pid})")
        time.sleep(0.5)
    
    print(f"\n✅ {len(AGENTS)} Agents 在线")
    print("   打开 http://localhost:8765/ 或终端输入 isa <你的名字>")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 关闭所有Agent...")

if __name__ == "__main__":
    main()
