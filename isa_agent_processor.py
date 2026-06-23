#!/usr/bin/env python3
"""
ISA Chat Agent 消息处理器 v1.0 — ISA 应用层消息处理引擎
=====================================================

定位：ISA Chat 的消息处理后端。不是"桥接器(ISA→外部平台)"——
      是 ISA Chat 自己的 Agent 认知管线。

历史：
  v0.1 (2026-06-20) 以 isa_yuanbao_bridge.py 命名——当时方向偏了：
    以为 ISA 需要"接入别人的通讯软件(元宝)"。
    实际方向：ISA Chat 自己就是通讯平台。
  v1.0 (2026-06-22) 重命名为 isa_agent_processor.py：
    回收核心代码，纠正定位。

架构:
  用户消息 → isa_agent_processor.py
    → Brain.ingest_signal (认知处理)
      → matched_cards (记忆匹配)
        → _generate_response (回复生成)

用法:
  # 单次消息处理（ISA Chat 后端调用）
  python isa_agent_processor.py --user "张三" --msg "我上次说的ISA三层架构是什么"

  # 持续监听模式（后台 daemon，legacy——被 Gateway WebSocket 取代）
  python isa_agent_processor.py --listen

数据:
  ~/.hermes/isa/users/<user_id>/
    brain/           每个用户的独立认知空间
    chat_log.jsonl   消息/回复日志（不可变追加）

设计原则：
  - 处理器只做"路由 + 认知管线"，不做前端
  - 每个用户有独立的 Brain 实例（身份隔离）
  - 消息是队列不是流（FIFO 信号队列）
  - 换设备→认知数据自动恢复（ISA Gateway 身份绑定）
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ISA Core 路径
ISA_DIR = Path.home() / "projects" / "isa"
sys.path.insert(0, str(ISA_DIR))

from brain import Brain
from isa import Signal, SignalGraph, DEFAULT_CHANNEL, extract_keywords

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

USER_DIR = Path.home() / ".hermes" / "isa" / "users"
USER_DIR.mkdir(parents=True, exist_ok=True)

# Agent 身份
AGENT_ID = "isa-bot"


# ═══════════════════════════════════════════════════════════════
# 用户认知空间
# ═══════════════════════════════════════════════════════════════

def _user_brain_dir(user_id: str) -> Path:
    """每个用户有独立的 Brain 目录（身份隔离）。"""
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "_-@.")
    return USER_DIR / safe_id / "brain"


def _chat_log(user_id: str, direction: str, content: str):
    """写聊天日志（不可变追加）。"""
    log_path = USER_DIR / _safe_user(user_id) / "chat_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "direction": direction,  # "in" | "out" | "system"
        "content": content[:500],
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _safe_user(user_id: str) -> str:
    return "".join(c for c in user_id if c.isalnum() or c in "_-@.")


# ═══════════════════════════════════════════════════════════════
# 核心：消息 → ISA 认知处理 → 回复
# ═══════════════════════════════════════════════════════════════

def process_message(user_id: str, message: str) -> dict:
    """处理一条用户消息。

    流程:
      1. 获取/创建用户的 Brain 实例
      2. 将消息作为 ISA Signal 摄入
      3. Brain.ingest_signal() → 记忆检索 → 匹配卡片
      4. 生成回复
      5. 日志记录

    Args:
        user_id: 用户 ID（消息发送者）
        message: 消息正文

    Returns:
        {"response": str, "matched_cards": list, "user_id": str}
    """
    brain_dir = _user_brain_dir(user_id)

    # 1. 创建/恢复 Brain 实例
    brain = Brain(agent_id=f"user:{user_id}", brain_dir=brain_dir)

    # 2. 写日志
    _chat_log(user_id, "in", message)

    # 3. 摄入信号 → 认知处理
    matched = brain.ingest_signal({
        "body": message,
        "source": user_id,
        "target": AGENT_ID,
        "type": "message",
    })

    # 4. 生成回复
    #    现阶段: 基于匹配卡片生成上下文感知回复
    #    将来: Brain 的完整认知管线 (dream → predict → decide)
    response = _generate_response(user_id, message, matched)

    # 5. 写日志
    _chat_log(user_id, "out", response)

    return {
        "response": response,
        "matched_cards": matched,
        "user_id": user_id,
    }


def _generate_response(user_id: str, message: str, matched: list[dict]) -> str:
    """基于匹配卡片生成回复。

    MVP 版: 简单规则 + 卡片上下文。
    将来版: Brain 的完整 NLG 管线。
    """
    # 关键词提取
    keywords = extract_keywords(message)

    # 问候检测
    greetings = ["你好", "hi", "hello", "hey", "在吗", "在不在"]
    is_greeting = any(g in message.lower() for g in greetings)

    if is_greeting:
        return (
            f"你好 {user_id}！我在。你跟我说过的每件事我都会记住，"
            f"哪怕你关掉这个窗口再打开。"
        )

    # 记忆查询检测
    memory_queries = ["记得", "还记得", "我说过", "上次", "之前", "你记不记得"]
    is_memory_query = any(q in message for q in memory_queries)

    if is_memory_query and matched:
        cards_str = "、".join([
            f"「{m['title']}」(匹配度{m['score']})"
            for m in matched[:2]
        ])
        return (
            f"我记得。这个话题和我的 {cards_str} 相关。"
            f"你想接着聊这个方向吗？"
        )
    elif is_memory_query and not matched:
        return (
            f"抱歉，我暂时没找到关于这个话题的记忆。"
            f"你跟我详细说说，我会记住的。"
        )

    # 关键词匹配——展示认知能力
    if matched:
        top_card = matched[0]
        return (
            f"收到。这个话题让我想起了「{top_card['title']}」"
            f"(匹配度{top_card['score']})。"
            f"你想深入讨论这个，还是说点别的？"
        )

    # 默认回复——承诺记忆
    return (
        f"收到。我已经记住了你刚才说的。"
        f"你随时可以问我「还记得吗」——我都在。"
    )


# ═══════════════════════════════════════════════════════════════
# 持续监听模式（Daemon）— LEGACY
# ═══════════════════════════════════════════════════════════════
# 注意: 此模式是 ISA Chat Gateway WebSocket 之前的轮询实现。
# Gateway 上线后，消息处理改为 WebSocket 推送→process_message 调用。
# listen_daemon 保留供无 Gateway 环境（纯 CLI 离线模式）使用。
# 新开发请用 Gateway WebSocket 模式。

def listen_daemon():
    """持续监听 ISA 频道，自动回复。

    LEGACY: 被 ISA Gateway WebSocket 取代。
    保留供 CLI 离线环境使用。
    """
    print("[isa-bot] 🎧 ISA Chat Agent 消息处理器启动")
    print(f"[isa-bot]    存储: {USER_DIR}")

    graph = SignalGraph(DEFAULT_CHANNEL, device_id="isa-agent-processor")
    graph.index.rebuild()

    last_seen = None

    try:
        while True:
            signals = graph.retrieve(target=AGENT_ID, limit=5)

            for sig in signals:
                if sig.source == AGENT_ID:
                    continue
                if last_seen and sig.timestamp <= last_seen:
                    continue

                user_id = sig.source
                message = sig.body

                print(f"\n  [{sig.timestamp[:19]}] 📩 {user_id}: {message[:60]}")

                result = process_message(user_id, message)

                print(f"  → 💬 {result['response'][:60]}")

                reply = Signal(
                    type="message",
                    source=AGENT_ID,
                    target=user_id,
                    body=result["response"],
                    meta={"via": "isa-agent-processor"},
                )
                graph.ingest(reply)
                graph.index.rebuild()

            if signals:
                last_seen = signals[0].timestamp

            time.sleep(2)

    except KeyboardInterrupt:
        print(f"\n[isa-bot] 已离线")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ISA Chat Agent 消息处理器 — ISA 认知管线的消息入口",
    )
    parser.add_argument("--user", help="用户 ID")
    parser.add_argument("--msg", help="消息内容")
    parser.add_argument("--listen", action="store_true",
                        help="持续监听模式（daemon，legacy）")
    parser.add_argument("--json", action="store_true",
                        help="JSON 输出模式")

    args = parser.parse_args()

    if args.listen:
        listen_daemon()
        return

    if args.user and args.msg:
        result = process_message(args.user, args.msg)
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"[isa-bot] 💬 {result['response']}")
            if result["matched_cards"]:
                for c in result["matched_cards"]:
                    print(f"          📇 {c['title']} (score={c['score']})")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
