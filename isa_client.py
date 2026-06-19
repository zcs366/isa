#!/usr/bin/env python3
"""
ISA v0.4.0 客户端库 — Hermes集成用
===================================
from isa_client import IsaClient

client = IsaClient("hermes-main")
client.send("agent-b", "你好")
client.wink("agent-b", "task-done", {"id": "x"})
client.resonate("全体注意")
for sig in client.poll():
    print(f"[{sig.type}] {sig.source}: {sig.body}")
"""

from isa import IsaAgent, SignalGraph, Signal
import time


class IsaClient:
    """ISA客户端——Hermes接入信号场的入口"""

    def __init__(self, agent_id: str, db_path: str = None):
        self.agent_id = agent_id
        graph = SignalGraph(db_path) if db_path else SignalGraph()
        self._agent = IsaAgent(agent_id, graph)

    def send(self, target: str, body: str, meta: dict = None) -> str:
        return self._agent.send(target, body, meta)

    def wink(self, target: str, signal: str = "ping", data: dict = None) -> str:
        return self._agent.wink(target, signal, data)

    def resonate(self, content: str, meta: dict = None) -> str:
        return self._agent.resonate(content, meta)

    def poll(self, *, signal_type: str = None, limit: int = 20) -> list[Signal]:
        return self._agent.poll(signal_type=signal_type, limit=limit)

    def search(self, query: str, limit: int = 20) -> list[Signal]:
        return self._agent.search(query, limit)

    def peers(self) -> list[str]:
        return self._agent.peers()

    def on_signal(self, handler):
        self._agent.on_signal(handler)

    def listen(self, interval: float = 0.5):
        return self._agent.listen(interval)

    def stop(self):
        self._agent.stop()

    def wait(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


if __name__ == "__main__":
    import sys
    client = IsaClient("hermes-cli")
    if len(sys.argv) >= 3 and sys.argv[1] == "send":
        client.send(sys.argv[2], " ".join(sys.argv[3:]))
        print("[OK]")
    elif len(sys.argv) >= 2 and sys.argv[1] == "poll":
        for s in client.poll():
            print(f"[{s.type}] {s.source}: {s.body}")
    elif len(sys.argv) >= 2 and sys.argv[1] == "peers":
        print(client.peers())
    elif len(sys.argv) >= 2 and sys.argv[1] == "listen":
        client.on_signal(lambda s: print(f"[{s.type}] {s.source}: {s.body}"))
        client.listen()
        client.wait()
    else:
        print("isa_client.py send <target> <content>")
        print("isa_client.py poll")
        print("isa_client.py peers")
        print("isa_client.py listen")
