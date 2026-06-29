#!/usr/bin/env python3
"""发送符合memo #002规范的wink"""
import json, os, sys
from datetime import datetime, timezone

RECALL = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")

def send_wink(from_agent, to_agent, subject, body, to_session="", requires_response=True):
    """发送规范wink"""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": "wink",
        "from_agent": from_agent,
        "to_agent": to_agent,
        "to_session": to_session,
        "subject": subject,
        "body": body,
        "requires_response": requires_response,
        "_written_by": from_agent
    }
    with open(RECALL, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"😉 wink: {from_agent}→{to_agent} ({subject})")
    return event

if __name__ == "__main__":
    # 示例：向子贡发送状态汇报
    send_wink(
        from_agent="sa_20260624",
        to_agent="zigong",
        subject="章鱼+三层通信栈+论文进展",
        body="子贡，当前状态：①章鱼完整闭环(FTS5+自动索引+hook集成+277篇喂食)②三层通信栈发现(物理层耳语+传输层wink+应用层章鱼)③论文草稿IAT已交付(7章+WMI数据)④vLLM 0.23.0安装成功. 你的进度？",
        requires_response=True
    )
