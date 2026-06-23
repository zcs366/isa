#!/usr/bin/env python3
"""项目Agent启动器 — 让每个项目在语义场有自己的Agent"""
import sys, json, asyncio, subprocess, os, signal, time
from pathlib import Path

ISA_DIR = Path.home() / "projects" / "isa"
GATEWAY = "ws://localhost:8765"

START_ALL = len(sys.argv) < 2 or sys.argv[1] == "--all"
SELECTED = [] if START_ALL else [a for a in sys.argv[1:] if not a.startswith("--")]

# 项目Agent阵容
AGENTS = {
    "老搭档": {"role": "常驻协作", "kw": {"协作":0.9,"方向":0.8,"把关":0.7}},
    "isa":     {"role": "ISA认知架构", "kw": {"isa":0.9,"波扩散":0.8,"gateway":0.7}},
    "ios":     {"role": "IO-S治理系统", "kw": {"ios":0.9,"cap":0.8,"审计":0.7}},
    "ita":     {"role": "ITA意图Token", "kw": {"ita":0.9,"意图":0.8,"token":0.7}},
    "iat":     {"role": "IAT语言压缩", "kw": {"iat":0.9,"压缩":0.8,"守恒律":0.7}},
    "iah":     {"role": "IAH注意力解剖", "kw": {"iah":0.9,"注意力":0.8,"解剖":0.7}},
    "idc":     {"role": "IDC三系统", "kw": {"idc":0.9,"三系统":0.8,"理论":0.7}},
    "iko":     {"role": "IKO交付管线", "kw": {"iko":0.9,"交付":0.8,"发布":0.7}},
    "搜神":     {"role": "情报搜索", "kw": {"搜神":0.9,"搜索":0.8,"情报":0.7}},
}

def launch(name, cfg):
    """启动一个项目Agent进程"""
    kw_json = json.dumps(cfg["kw"])
    script = f"""
import sys, json, asyncio, time
sys.path.insert(0, '{ISA_DIR}')
from isa import IsaAgent, SignalGraph
from dataclasses import asdict

async def run():
    import websockets
    from isa import Signal
    async with websockets.connect('{GATEWAY}/isa/channel/projects') as ws:
        await ws.send(json.dumps({{'type':'register','agent_id':'{name}','channel':'projects','keywords':{kw_json}}}))
        reply = json.loads(await ws.recv())
        print(f'[{name}] ✅ 上线 (peers={{reply.get("peer_count",0)}})')
        graph = SignalGraph('projects', device_id='{name}')
        agent = IsaAgent('{name}', graph=graph)
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                msg = json.loads(raw)
                if msg.get('type')=='message' and msg.get('source')!='{name}':
                    agent.brain.ingest_signal(asdict(Signal(type='message',source=msg.get('source','?'),target='{name}',body=msg.get('body',''))))
            except asyncio.TimeoutError:
                agent.brain.dream()
asyncio.run(run())
"""
    return subprocess.Popen([sys.executable, "-c", script],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    targets = SELECTED if SELECTED else list(AGENTS.keys())
    procs = []
    for name in targets:
        if name in AGENTS:
            p = launch(name, AGENTS[name])
            procs.append((name, p))
            print(f"   🟢 {name} ({AGENTS[name]['role']}) PID={p.pid}")
        else:
            print(f"   ⚠️ 未知Agent: {name}")
    
    print(f"\n   ✅ {len(procs)} 项目Agent上线")
    print(f"   频道: projects")
    print(f"   打开 http://localhost:8765/ → 频道: projects")
    print(f"   或: isa <你的名字> --channel projects")
    
    def cleanup(s, f):
        for n, p in procs:
            p.terminate()
        sys.exit(0)
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup(None, None)

if __name__ == "__main__":
    main()
