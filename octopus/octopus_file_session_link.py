#!/usr/bin/env python3
"""章鱼文件↔会话关联器 v0.1 — P2-2

功能: 当搜索结果命中文件时，查出该文件在哪些session中被讨论过。

用法:
  python3 octopus_file_session_link.py <文件路径>   # 查指定文件的会话记录
  python3 octopus_file_session_link.py --stats       # 统计关联覆盖率

依赖: state.db (Hermes会话数据库)
"""
import os, sys, sqlite3, re
from datetime import datetime

STATE_DB = os.path.expanduser("~/.hermes/state.db")
TENTACLES = os.path.expanduser("~/projects/isa/octopus/tentacles")

def find_session_refs(filepath):
    """查找文件路径在session中的出现记录"""
    if not os.path.exists(STATE_DB):
        return []
    
    # 提取文件名用于搜索
    fname = os.path.basename(filepath)
    fname_noext = os.path.splitext(fname)[0]
    
    results = []
    try:
        conn = sqlite3.connect(STATE_DB)
        conn.row_factory = sqlite3.Row
        
        # 搜索消息内容中包含文件路径或文件名
        for keyword in [filepath[-80:], fname, fname_noext]:
            if len(keyword) < 5:
                continue
            cursor = conn.execute(
                "SELECT m.id, m.session_id, m.role, m.content, m.timestamp, s.title "
                "FROM messages m "
                "LEFT JOIN sessions s ON m.session_id = s.id "
                "WHERE m.content LIKE ? AND m.role IN ('user', 'assistant') "
                "ORDER BY m.timestamp DESC LIMIT 10",
                (f"%{keyword}%",)
            )
            for row in cursor:
                content_preview = row["content"][:200] if row["content"] else ""
                ts = datetime.fromtimestamp(row["timestamp"]).strftime("%m-%d %H:%M") if row["timestamp"] else "?"
                title = row["title"][:40] if row["title"] else row["session_id"][:16]
                results.append({
                    "session_id": row["session_id"],
                    "title": title,
                    "role": row["role"],
                    "time": ts,
                    "preview": content_preview[:120]
                })
        conn.close()
    except Exception as e:
        return [{"error": str(e)}]
    
    # 去重
    seen = set()
    unique = []
    for r in results:
        key = (r["session_id"], r["preview"][:30])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:5]

def cross_link_search_results(query):
    """搜索同时返回文件结果和它们的会话关联"""
    import subprocess
    
    # 先用章鱼搜索
    r = subprocess.run(
        ["python3", "octopus_search.py", query],
        capture_output=True, text=True, timeout=30,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    lines = r.stdout.split("\n")
    file_results = [l for l in lines if "[FILES]" in l or "[文档]" in l or "[RECALL]" in l]
    
    print(f"\n🔗 文件↔会话关联: {query}")
    print("=" * 50)
    
    for line in file_results[:10]:
        # 提取文件路径
        path_match = re.search(r'(/[^\s]+\.\w+)', line)
        if path_match:
            fp = path_match.group(1)
            refs = find_session_refs(fp)
            if refs:
                print(f"\n  📄 {os.path.basename(fp)}")
                for ref in refs[:3]:
                    print(f"    💬 [{ref['time']}] {ref['title'][:30]}... ({ref['role']})")
                    print(f"       {ref['preview'][:80]}")
    
    return file_results

def stats():
    """统计文件/会话关联覆盖率"""
    import glob
    
    # 统计文档文件数
    doc_count = 0
    for root, dirs, files in os.walk(TENTACLES):
        doc_count += len([f for f in files if f.endswith('.md')])
    
    # 统计会话数
    if not os.path.exists(STATE_DB):
        print("❌ state.db not found")
        return
    
    conn = sqlite3.connect(STATE_DB)
    session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    conn.close()
    
    print(f"\n📊 章鱼关联统计")
    print(f"  触须文档: {doc_count} 篇")
    print(f"  会话数:   {session_count}")
    print(f"  消息数:   {msg_count}")
    print(f"  P2-2状态: 脚本已就绪，待集成到搜索管线")

if __name__ == "__main__":
    if "--stats" in sys.argv:
        stats()
    elif len(sys.argv) > 1:
        refs = find_session_refs(sys.argv[1])
        if refs:
            print(f"\n📎 '{os.path.basename(sys.argv[1])}' 在以下会话中被讨论:")
            for r in refs:
                print(f"  [{r['time']}] {r['title'][:40]} ({r['role']})")
                print(f"    {r['preview'][:100]}")
        else:
            print(f"\n未找到 '{sys.argv[1]}' 的会话记录")
    else:
        print("用法:")
        print("  python3 octopus_file_session_link.py <文件路径>   # 查会话记录")
        print("  python3 octopus_file_session_link.py --stats       # 统计")
        print("  python3 octopus_file_session_link.py <关键词>      # 关联搜索")
