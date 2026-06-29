#!/usr/bin/env python3
"""
章鱼本地搜索系统 — 八只触角

用法:
  python3 octopus.py write <tentacle> <title> <content>  # 写文档
  python3 octopus.py search <query>                       # 搜索
  python3 octopus.py list [tentacle]                      # 列出文档
  python3 octopus.py index                                # 重建索引
"""

import json, os, sys, sqlite3, glob
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
TENTACLES = BASE / "tentacles"
TEMPLATES = BASE / "templates"
REGISTRY = BASE / "registry.json"
DB_PATH = BASE / "octopus.db"

VALID_TENTACLES = ["memo", "pal", "analysis", "intel", "execution", "meeting", "techdoc", "lesson"]

# ─── 数据库 ─────────────────────────────────────────

def init_db():
    """初始化 FTS5 数据库"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
            path, tentacle, title, date, content,
            tokenize='unicode61'
        )
    """)
    conn.commit()
    return conn

def index_file(conn, filepath, tentacle):
    """索引单个文件"""
    path = str(filepath)
    with open(filepath) as f:
        content = f.read()

    # 提取标题（第一行 # 开头）
    title = ""
    for line in content.split("\n"):
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # 提取日期（从文件名或内容）
    fname = filepath.name
    date = ""
    if len(fname) >= 10:
        date = fname[:10]

    # 从内容中提取日期
    if not date:
        for line in content.split("\n"):
            if "日期" in line and "：" in line:
                date = line.split("：")[-1].strip()[:10]
                break

    # 写入 FTS
    conn.execute("DELETE FROM docs_fts WHERE path = ?", (path,))
    conn.execute(
        "INSERT INTO docs_fts (path, tentacle, title, date, content) VALUES (?, ?, ?, ?, ?)",
        (path, tentacle, title, date, content)
    )

def rebuild_index(conn):
    """重建全部索引"""
    count = 0
    for tentacle in VALID_TENTACLES:
        tentacle_dir = TENTACLES / tentacle
        if not tentacle_dir.exists():
            continue
        for f in tentacle_dir.glob("*.md"):
            index_file(conn, f, tentacle)
            count += 1
    conn.commit()
    return count

# ─── 注册表 ─────────────────────────────────────────

def load_registry():
    if REGISTRY.exists():
        with open(REGISTRY) as f:
            return json.load(f)
    return {"docs": [], "updated": ""}

def save_registry(reg):
    reg["updated"] = datetime.now(timezone.utc).isoformat()
    with open(REGISTRY, "w") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

def add_to_registry(tentacle, title, path):
    reg = load_registry()
    reg["docs"].append({
        "tentacle": tentacle,
        "title": title,
        "path": str(path),
        "created": datetime.now(timezone.utc).isoformat()
    })
    save_registry(reg)

# ─── 命令 ───────────────────────────────────────────

def cmd_write(args):
    """写文档"""
    if len(args) < 3:
        print("用法: octopus.py write <tentacle> <title> [content]")
        print(f"触角: {', '.join(VALID_TENTACLES)}")
        return

    tentacle = args[0]
    title = args[1]
    content = " ".join(args[2:]) if len(args) > 2 else ""

    if tentacle not in VALID_TENTACLES:
        print(f"❌ 无效触角: {tentacle}")
        print(f"有效触角: {', '.join(VALID_TENTACLES)}")
        return

    # 文件名
    date = datetime.now().strftime("%Y-%m-%d")
    safe_title = title.replace(" ", "_").replace("/", "_")[:30]
    filename = f"{date}_{tentacle}_{safe_title}.md"
    filepath = TENTACLES / tentacle / filename

    # 如果内容是 "-" 开头，从 stdin 读
    if content.startswith("-"):
        content = sys.stdin.read()

    # 如果内容为空，从模板开始
    if not content:
        template_path = TEMPLATES / f"{tentacle}.md"
        if template_path.exists():
            with open(template_path) as f:
                content = f.read()
            # 替换占位符
            content = content.replace("{标题}", title)
            content = content.replace("{日期}", date)
            content = content.replace("{签发人}", "军师")
            content = content.replace("{制作人}", "军师")
            content = content.replace("{分析人}", "军师")
            content = content.replace("{情报官}", "军师")
            content = content.replace("{执行人}", "军师")
            content = content.replace("{记录人}", "军师")
            content = content.replace("{作者}", "军师")
        else:
            content = f"# {title}\n\n> 日期：{date}\n\n{content}"

    # 写文件
    os.makedirs(filepath.parent, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)

    # 索引
    conn = init_db()
    index_file(conn, filepath, tentacle)
    conn.commit()
    conn.close()

    # 注册
    add_to_registry(tentacle, title, filepath)

    print(f"✅ {tentacle}/{filename}")
    print(f"   路径: {filepath}")
    print(f"   大小: {os.path.getsize(filepath)} bytes")

def cmd_search(args):
    """搜索"""
    if not args:
        print("用法: octopus.py search <query>")
        return

    query = " ".join(args)
    conn = init_db()

    try:
        rows = conn.execute(
            "SELECT path, tentacle, title, date, snippet(docs_fts, 4, '>>>', '<<<', '...', 40) "
            "FROM docs_fts WHERE docs_fts MATCH ? ORDER BY rank LIMIT 20",
            (query,)
        ).fetchall()
    except sqlite3.OperationalError:
        # FTS5 语法错误，用 LIKE 兜底
        rows = conn.execute(
            "SELECT path, tentacle, title, date, substr(content, 1, 200) "
            "FROM docs_fts WHERE content LIKE ? LIMIT 20",
            (f"%{query}%",)
        ).fetchall()

    conn.close()

    if not rows:
        print(f"无结果: {query}")
        return

    print(f"搜索: {query} ({len(rows)} 条)")
    print("=" * 60)
    for path, tentacle, title, date, snippet in rows:
        print(f"\n  [{tentacle}] {title}")
        print(f"  日期: {date}")
        print(f"  路径: {path}")
        print(f"  摘要: {snippet[:120]}...")

def cmd_list(args):
    """列出文档"""
    tentacle = args[0] if args else None

    conn = init_db()
    if tentacle:
        rows = conn.execute(
            "SELECT path, tentacle, title, date FROM docs_fts WHERE tentacle = ? ORDER BY date DESC",
            (tentacle,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT path, tentacle, title, date FROM docs_fts ORDER BY date DESC"
        ).fetchall()
    conn.close()

    if not rows:
        print("无文档")
        return

    # 按触角分组
    by_tentacle = {}
    for path, t, title, date in rows:
        if t not in by_tentacle:
            by_tentacle[t] = []
        by_tentacle[t].append((title, date, path))

    for t in VALID_TENTACLES:
        if t not in by_tentacle:
            continue
        docs = by_tentacle[t]
        print(f"\n{'='*40}")
        print(f"  {t} ({len(docs)} 篇)")
        print(f"{'='*40}")
        for title, date, path in docs[:10]:
            print(f"  [{date}] {title}")
            print(f"           {path}")
        if len(docs) > 10:
            print(f"  ... 还有 {len(docs)-10} 篇")

def cmd_index(args):
    """重建索引"""
    conn = init_db()
    count = rebuild_index(conn)
    conn.close()
    print(f"✅ 索引重建完成: {count} 篇文档")

def main():
    if len(sys.argv) < 2:
        print("章鱼本地搜索系统 — 八只触角")
        print()
        print("用法:")
        print("  python3 octopus.py write <tentacle> <title> [content]")
        print("  python3 octopus.py search <query>")
        print("  python3 octopus.py list [tentacle]")
        print("  python3 octopus.py index")
        print()
        print(f"触角: {', '.join(VALID_TENTACLES)}")
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "write":
        cmd_write(args)
    elif cmd == "search":
        cmd_search(args)
    elif cmd == "list":
        cmd_list(args)
    elif cmd == "index":
        cmd_index(args)
    else:
        print(f"未知命令: {cmd}")

if __name__ == "__main__":
    main()
