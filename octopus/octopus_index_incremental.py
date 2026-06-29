#!/usr/bin/env python3
"""章鱼增量索引 v3.1 — Tantivy 增量追加（RECALL + SESSION）
用法: python3 octopus_index_incremental.py
      python3 octopus_index_incremental.py --last-n 5

维护两个增量索引:
  - RECALL 行级增量（原逻辑）
  - SESSION 消息级增量（从 state.db messages 表读新消息）
"""
import os, json, sys
import tantivy
import jieba
import sqlite3

RECALL = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")
STATE_DB = os.path.expanduser("~/.hermes/state.db")
INDEX_DIR = os.path.expanduser("~/projects/isa/octopus/tantivy_index")
STATE = os.path.expanduser("~/projects/isa/octopus/.index_state.json")


# ─── RECALL 部分（原逻辑，不变） ──────────────────────────

def build_recall_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("body", stored=True)
    return builder.build()


def get_recall_text(obj):
    parts = []
    for k in ("type", "agent", "agent_id", "event", "detail", "summary",
              "content", "subject", "body", "law_name", "conclusion",
              "summary_short"):
        v = obj.get(k)
        if v and isinstance(v, str):
            parts.append(v)
    cards = obj.get("card_ids") or obj.get("cards") or obj.get("card")
    if cards:
        if isinstance(cards, list):
            parts.extend(cards)
        elif isinstance(cards, str):
            parts.append(cards)
    for k in ("payload", "deliverables"):
        v = obj.get(k)
        if v and isinstance(v, dict):
            for sk in ("summary", "topic", "content"):
                sv = v.get(sk)
                if sv and isinstance(sv, str):
                    parts.append(sv)
    return " ".join(parts)


def get_recall_id(obj):
    return str(obj.get("ts", obj.get("line_no", str(hash(str(obj))))))


def index_recall_lines(from_line, to_line):
    """增量索引 RECALL 行"""
    recall_path = os.path.join(INDEX_DIR, "recall")
    if not os.path.exists(recall_path):
        # 首次，全量构建
        import subprocess as _sp
        _sp.run([sys.executable, os.path.join(
            os.path.dirname(__file__), "octopus_index.py")])
        return 0

    schema = build_recall_schema()
    index = tantivy.Index(schema, path=recall_path)
    writer = index.writer()
    count = 0
    with open(RECALL) as f:
        for i, line in enumerate(f, 1):
            if i <= from_line:
                continue
            if i > to_line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = get_recall_text(obj)
            if not text:
                continue
            doc_id = get_recall_id(obj)
            segmented = " ".join(jieba.cut(text))
            writer.add_document(tantivy.Document(id=doc_id, body=segmented))
            count += 1
    writer.commit()
    return count


# ─── SESSION 增量索引 ────────────────────────────────────

def build_sessions_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("session_id", stored=True)
    builder.add_text_field("role", stored=True)
    builder.add_text_field("body", stored=True)
    builder.add_integer_field("ts", stored=True)
    return builder.build()


def get_last_session_id():
    """从状态文件读取上次索引的 session message_id"""
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f).get("last_session_id", 0)
    return 0


def save_session_state(msg_id):
    """保存 session 增量索引状态"""
    state = {}
    if os.path.exists(STATE):
        with open(STATE) as f:
            state = json.load(f)
    state["last_session_id"] = msg_id
    with open(STATE, "w") as f:
        json.dump(state, f)


def get_last_recall_line():
    """读取现有 RECALL last_line 状态"""
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f).get("last_line", 0)
    return 0


def save_recall_state(line_no):
    """保存 RECALL 增量索引状态"""
    state = {}
    if os.path.exists(STATE):
        with open(STATE) as f:
            state = json.load(f)
    state["last_line"] = line_no
    with open(STATE, "w") as f:
        json.dump(state, f)


def get_max_message_id():
    """获取 state.db 中最新 message_id"""
    if not os.path.exists(STATE_DB):
        return 0
    try:
        conn = sqlite3.connect(STATE_DB)
        cursor = conn.execute("SELECT MAX(id) FROM messages")
        max_id = cursor.fetchone()[0] or 0
        conn.close()
        return max_id
    except Exception:
        return 0


def index_new_sessions():
    """增量索引新的 session 消息"""
    sessions_path = os.path.join(INDEX_DIR, "sessions")
    if not os.path.exists(sessions_path):
        # 首次，全量构建
        import subprocess as _sp
        _sp.run([sys.executable, os.path.join(
            os.path.dirname(__file__), "octopus_index.py")])
        return 0

    last_id = get_last_session_id()
    max_id = get_max_message_id()
    if last_id >= max_id:
        return 0

    schema = build_sessions_schema()
    index = tantivy.Index(schema, path=sessions_path)
    writer = index.writer()
    count = 0
    try:
        conn = sqlite3.connect(STATE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, session_id, role, content, timestamp "
            "FROM messages "
            "WHERE id > ? AND content IS NOT NULL AND content != '' "
            "AND role IN ('user', 'assistant', 'tool') "
            "ORDER BY id",
            (last_id,)
        )
        for row in cursor:
            content = row["content"]
            if not content or len(content.strip()) < 5:
                continue
            text = content[:2000]
            segmented = " ".join(jieba.cut(text))
            ts = int(row["timestamp"])
            writer.add_document(tantivy.Document(
                id=str(row["id"]),
                session_id=str(row["session_id"]),
                role=str(row["role"]),
                body=segmented,
                ts=ts,
            ))
            count += 1
        conn.close()
        writer.commit()
        if count > 0:
            save_session_state(max_id)
    except Exception as e:
        print(f"  ⚠️  session 增量索引异常: {e}")
        return 0

    return count


def main():
    # ========== RECALL 增量索引（原逻辑） ==========
    with open(RECALL) as f:
        total_lines = sum(1 for _ in f)
    recall_last = get_last_recall_line()
    if recall_last < total_lines:
        # --last-n 模式
        if len(sys.argv) > 1 and sys.argv[1] == "--last-n":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            from_line = max(0, total_lines - n)
        else:
            from_line = recall_last
        recall_count = index_recall_lines(from_line, total_lines)
        save_recall_state(total_lines)
        print(f"🐙 RECALL 增量: L{from_line+1}-L{total_lines} ({recall_count}条)")
    else:
        print(f"🐙 RECALL 增量: 无新行")

    # ========== SESSION 增量索引（新！） ==========
    sess_count = index_new_sessions()
    if sess_count > 0:
        print(f"🐙 SESSION 增量: {sess_count} 条新对话消息")
    else:
        print(f"🐙 SESSION 增量: 无新消息")


if __name__ == "__main__":
    main()
