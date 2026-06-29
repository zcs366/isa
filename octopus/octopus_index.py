#!/usr/bin/env python3
"""章鱼索引构建器 v3.5 — Tantivy 全文索引（中文分词支持）
用法: python3 octopus_index.py [rebuild] [--quick]

数据源:
  1. RECALL.jsonl ← 事件摘要日志
  2. state.db     ← session对话原文
  3. tentacles/*.md ← 触须文档
  4. 文件系统     ← 本地所有文件（C/D/I盘）
"""
import os, json, glob, shutil, time, re
import tantivy
import jieba
import sqlite3

RECALL = os.path.expanduser("~/.hermes/jiak/RECALL.jsonl")
STATE_DB = os.path.expanduser("~/.hermes/state.db")
OCTOPUS = os.path.expanduser("~/projects/isa/octopus/tentacles")
TEMPLATES = os.path.expanduser("~/projects/isa/octopus/templates")
REFERENCES = os.path.expanduser("~/.hermes/skills/knowledge-management/octopus-local-search/references")
INDEX_DIR = os.path.expanduser("~/projects/isa/octopus/tantivy_index")


# ─── RECALL 索引（原逻辑不变） ──────────────────────────

def get_recall_id(obj):
    return str(obj.get("ts", obj.get("line_no", str(hash(str(obj))))))

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


# ─── Schema 构建 ────────────────────────────────────────

def build_recall_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("body", stored=True)
    return builder.build()

def build_sessions_schema():
    """session对话原文索引 schema"""
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)          # message_id
    builder.add_text_field("session_id", stored=True)   # 分组用
    builder.add_text_field("role", stored=True)         # user/assistant/tool
    builder.add_text_field("body", stored=True)         # 对话原文（可搜索+可展示）
    builder.add_integer_field("ts", stored=True)        # timestamp 用于排序
    return builder.build()

def build_docs_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("title", stored=True)
    builder.add_text_field("tentacle", stored=True)
    builder.add_text_field("body", stored=True)
    return builder.build()


def create_index(schema, path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    return tantivy.Index(schema, path=path)


# ─── 索引构建器 ─────────────────────────────────────────

def index_recall(index):
    """索引 RECALL.jsonl"""
    count = 0
    writer = index.writer()
    with open(RECALL) as f:
        for line in f:
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
            writer.add_document(tantivy.Document(
                id=doc_id,
                body=segmented,
            ))
            count += 1
    writer.commit()
    return count


def index_sessions(index):
    """索引 session 对话原文（从 state.db messages 表读取）"""
    count = 0
    if not os.path.exists(STATE_DB):
        print(f"  ⚠️  state.db 不存在: {STATE_DB}")
        return 0

    writer = index.writer(heap_size=128 * 1024 * 1024)  # 128MB heap，一次提交14万条
    try:
        conn = sqlite3.connect(STATE_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, session_id, role, content, timestamp "
            "FROM messages "
            "WHERE content IS NOT NULL AND content != '' "
            "AND role IN ('user', 'assistant', 'tool') "
            "ORDER BY id"
        )
        for row in cursor:
            content = row["content"]
            if not content or len(content.strip()) < 5:
                continue
            # 截断超长 content（tool output 可能几万字符）
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
        writer.commit()  # commit 放在 try 内，失败时能捕获
    except Exception as e:
        print(f"  ⚠️  session 索引异常: {e}")
        return count
    return count


def index_docs(index, base_dir, tentacle_label=None):
    """索引 md 文档目录"""
    count = 0
    writer = index.writer()
    for md in glob.glob(os.path.join(base_dir, "**", "*.md"), recursive=True):
        try:
            with open(md) as f:
                content = f.read()
        except Exception:
            continue
        title = ""
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break
        tentacle = ""
        if tentacle_label:
            tentacle = tentacle_label
        elif base_dir == OCTOPUS:
            rel = os.path.relpath(md, OCTOPUS)
            parts = rel.split(os.sep)
            if parts:
                tentacle = parts[0]
        elif base_dir == TEMPLATES:
            tentacle = "template"
        else:
            tentacle = "reference"

        segmented = " ".join(jieba.cut(content))
        writer.add_document(tantivy.Document(
            id=md,
            title=title,
            tentacle=tentacle,
            body=segmented,
        ))
        count += 1
    writer.commit()
    return count


# ─── FILES 文件索引（第五路·v3.5） ─────────────────────

def build_files_schema():
    """本地文件索引 schema"""
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)       # 文件路径
    builder.add_text_field("name", stored=True)     # 文件名
    builder.add_text_field("ext", stored=True)      # 扩展名
    builder.add_text_field("fmt", stored=True)      # 格式: text/pdf/docx/ocr
    builder.add_text_field("body", stored=True)     # 文本内容（分词后）
    builder.add_integer_field("size", stored=True)  # 文件大小
    builder.add_integer_field("mtime", stored=True) # 修改时间
    return builder.build()


# 扫描目录
FILES_SCAN_DIRS = [
    "/mnt/c/Users/Administrator/Desktop",
    "/mnt/c/Users/Administrator/Documents",
    "/mnt/c/Users/Administrator/Downloads",
    "/mnt/d",
    os.path.expanduser("~"),
    "/mnt/i/hermes",
]

# 文本格式（直接读）
FILES_TEXT_EXTS = {
    ".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".csv", ".xml", ".html", ".css", ".sh", ".env",
    ".cfg", ".ini", ".conf", ".log", ".sql", ".tex",
    ".c", ".cpp", ".h", ".java", ".rs", ".go", ".rb", ".lua",
}


def extract_file_text(filepath):
    """从文件提取文本"""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext in FILES_TEXT_EXTS:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read(4096).strip(), "text"
        except Exception:
            return "", "text"
    
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(filepath)
            text = "".join(p.get_text() for p in doc)[:4096]
            doc.close()
            return text.strip(), "pdf"
        except Exception:
            return "", "pdf"
    
    if ext == ".docx":
        try:
            from docx import Document
            doc = Document(filepath)
            text = "\n".join(p.text for p in doc.paragraphs)[:4096]
            return text.strip(), "docx"
        except Exception:
            return "", "docx"
    
    return "", "binary"


def index_files(index):
    """扫描本地文件并建 Tantivy 索引（第五路）"""
    count = 0
    writer = index.writer(heap_size=64 * 1024 * 1024)
    exclude_dirs = re.compile(
        r"(node_modules|\.git|__pycache__|venv|\.venv|\.cache|"
        r"AppData|Windows|Program)", re.IGNORECASE)
    
    for scan_dir in FILES_SCAN_DIRS:
        if not os.path.exists(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir, topdown=True):
            dirs[:] = [d for d in dirs if not exclude_dirs.search(os.path.join(root, d))]
            for fname in files:
                fp = os.path.join(root, fname)
                try:
                    fsize = os.path.getsize(fp)
                    if fsize > 50 * 1024 * 1024:
                        continue
                    mtime = int(os.path.getmtime(fp))
                except OSError:
                    continue
                ext = os.path.splitext(fname)[1].lower()
                
                text, fmt = extract_file_text(fp)
                if not text and fmt == "binary":
                    continue
                
                segmented = " ".join(jieba.cut(text[:2000]))
                writer.add_document(tantivy.Document(
                    id=fp,
                    name=fname,
                    ext=ext,
                    fmt=fmt,
                    body=segmented,
                    size=fsize,
                    mtime=mtime,
                ))
                count += 1
                if count % 5000 == 0:
                    print(f"   已索引 {count} 文件...")
    
    writer.commit()
    return count


def main():
    rebuild = "rebuild" in sys.argv
    quick = "--quick" in sys.argv

    print("🐙 章鱼索引构建 v3.5 (Tantivy + session原文 + 本地文件)...")

    # ========== RECALL 索引 ==========
    recall_path = os.path.join(INDEX_DIR, "recall")
    recall_schema = build_recall_schema()
    recall_index = create_index(recall_schema, recall_path)
    r1 = index_recall(recall_index)
    print(f"✅ RECALL 索引: {r1} 条 (路径: {recall_path})")

    # ========== Session 对话索引（新！） ==========
    sessions_path = os.path.join(INDEX_DIR, "sessions")
    sessions_schema = build_sessions_schema()
    sessions_index = create_index(sessions_schema, sessions_path)
    r_session = index_sessions(sessions_index)
    print(f"✅ SESSION 索引: {r_session} 条对话原文 (路径: {sessions_path})")

    # ========== 文档索引 ==========
    docs_path = os.path.join(INDEX_DIR, "docs")
    docs_schema = build_docs_schema()
    docs_index = create_index(docs_schema, docs_path)

    r2 = index_docs(docs_index, OCTOPUS)
    r3 = index_docs(docs_index, TEMPLATES, tentacle_label="template")
    r4 = index_docs(docs_index, REFERENCES, tentacle_label="reference")
    print(f"✅ 文档索引: tentacles={r2} + templates={r3} + references={r4} = {r2+r3+r4} 篇 (路径: {docs_path})")

    total_docs = r2 + r3 + r4
    
    # ========== Δ胶囊共振胶囊索引（第六路·v3.6） ==========
    resonance_count = 0
    try:
        caps_path = os.path.expanduser("~/.hermes/semantic_field/resonance_capsules.json")
        if os.path.exists(caps_path):
            import json as _json
            resonance_path = os.path.join(INDEX_DIR, "resonance")
            builder = tantivy.SchemaBuilder()
            builder.add_text_field("id", stored=True)
            builder.add_text_field("source", stored=True)
            builder.add_text_field("target", stored=True)
            builder.add_text_field("intent", stored=True)
            builder.add_text_field("body", stored=True)
            builder.add_integer_field("ts", stored=True)
            res_schema = builder.build()
            res_index = create_index(res_schema, resonance_path)
            res_writer = res_index.writer()
            with open(caps_path) as f:
                caps = _json.load(f)
            for c in caps:
                text = c.get("content", {}).get("text", "")
                if not text: continue
                body = " ".join(jieba.cut(text))
                res_writer.add_document(tantivy.Document(
                    id=c.get("capsule_id", "?"),
                    source=c.get("source_channel", "?"),
                    target=c.get("target_channel", "?"),
                    intent=c.get("content", {}).get("intent", "?"),
                    body=body,
                    ts=int(c.get("timestamp", 0)),
                ))
                resonance_count += 1
            res_writer.commit()
            print(f"✅ Δ胶囊索引: {resonance_count} 枚胶囊 (路径: {resonance_path})")
    except Exception as e:
        print(f"⚠ Δ胶囊索引: 跳过 ({e})")

    # ========== 本地文件索引（第五路·v3.5） ==========
    print(f"\n📊 总计: RECALL {r1} 条 + SESSION {r_session} 条 + 文档 {total_docs} 篇 + Δ胶囊 {resonance_count} 枚", end="")
    print(" (--quick, 跳过本地文件索引)")

    print(f"\n📁 索引目录: {INDEX_DIR}")

    # 同步 state 文件，防增量索引重复
    try:
        import sqlite3 as _sql
        if os.path.exists(STATE_DB):
            _conn = _sql.connect(STATE_DB)
            _max_id = _conn.execute("SELECT MAX(id) FROM messages").fetchone()[0] or 0
            _conn.close()
            _state = {}
            if os.path.exists(".index_state.json"):
                with open(".index_state.json") as _f:
                    _state = json.load(_f)
            _state["last_session_id"] = _max_id
            with open(".index_state.json", "w") as _f:
                json.dump(_state, _f)
            print(f"📌 state 已同步: last_session_id={_max_id}")
    except Exception as _e:
        print(f"  ⚠️  state 同步跳过: {_e}")


if __name__ == "__main__":
    import sys
    main()
