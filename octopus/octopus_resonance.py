#!/usr/bin/env python3
"""章鱼内外共鸣引擎 v0.1 — P2-3

功能: 外部搜索结果 × 内部经验(文档+SESSION)交叉引用
当外部Web结果与内部文档/会议在语义上相似时，标记为'内外共鸣'。

用法:
  python3 octopus_resonance.py <关键词>     # 内外共鸣搜索
  python3 octopus_resonance.py <关键词> --web  # 只搜外部+共鸣

依赖: BGE-small-zh (P2-1), octopus_search.py, web_search
"""
import sys, os, json, subprocess
import numpy as np

HOME = os.path.expanduser("~")
OCTOPUS = os.path.expanduser("~/projects/isa/octopus")
EMBED_CACHE = os.path.expanduser("~/.hermes/octopus/semantic_embeddings.pkl")
RESONANCE_THRESHOLD = 0.45  # BGE余弦相似度高于此=可能共鸣

_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(
            "/mnt/d/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/7999e1d3359715c523056ef9478215996d62a620",
            device="cpu")
    return _model

def search_internal(query):
    """搜索内部经验(八文档优先)"""
    # 直接用文件搜索(tentacles目录)
    import glob
    doc_results = []
    for root, dirs, files in os.walk(os.path.expanduser("~/projects/isa/octopus/tentacles")):
        for f in files:
            if f.endswith('.md'):
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', errors='replace') as fh:
                        content = fh.read()
                    if query in content:
                        rel = os.path.relpath(fp, os.path.expanduser("~"))
                        doc_results.append(("文档", fp, rel[:80]))
                except:
                    pass
    return doc_results[:10]

def search_web(query):
    """搜索外部Web"""
    import urllib.request, urllib.parse
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        results = data.get("RelatedTopics", [])
        web_items = []
        for item in results[:5]:
            if "Text" in item and "FirstURL" in item:
                web_items.append((item.get("Text", "")[:80], item.get("FirstURL", ""), ""))
            elif "Topics" in item:
                for sub in item["Topics"][:3]:
                    web_items.append((sub.get("Text", "")[:80], sub.get("FirstURL", ""), ""))
        return web_items if web_items else [(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}", "", "")]
    except:
        return [(f"于(duckduckgo search: {query[:30]}...)", "", "")]

def compute_resonance(query, web_title, web_desc):
    """计算外部结果与内部经验的语义共鸣度"""
    model = get_model()
    
    # 搜索内部
    internal = search_internal(query)
    if not internal:
        return []
    
    # 编码外部文本
    ext_text = f"{web_title} {web_desc}"[:500]
    if not ext_text.strip():
        return []
    ext_emb = model.encode([ext_text], normalize_embeddings=True)[0]
    
    # 编码内部文档(读前2000字)
    import glob
    resonances = []
    for src_type, path, label in internal[:5]:
        if src_type == "文档" and os.path.exists(path):
            try:
                with open(path, 'r', errors='replace') as f:
                    int_text = f.read()[:2000]
                int_emb = model.encode([int_text], normalize_embeddings=True)[0]
                sim = float(np.dot(ext_emb, int_emb))
                if sim > RESONANCE_THRESHOLD:
                    rel_path = os.path.relpath(path, HOME) if HOME in path else path
                    resonances.append((sim, src_type, rel_path[:80]))
            except:
                pass
    
    return sorted(resonances, key=lambda x: -x[0])

def main():
    if len(sys.argv) < 2:
        print("用法: python3 octopus_resonance.py <关键词>")
        sys.exit(1)
    
    query = " ".join([a for a in sys.argv[1:] if not a.startswith("--")])
    
    print(f"🎵 章鱼内外共鸣引擎 v0.1: {query}")
    print("=" * 50)
    
    # 搜外部Web
    web_items = search_web(query)
    print(f"\n🌐 外部搜索结果: {len(web_items)} 条")
    
    for title, url, desc in web_items[:3]:
        print(f"\n  {title[:60]}")
        print(f"  {url[:60]}")
        
        # 计算共鸣
        resonances = compute_resonance(query, title, desc)
        if resonances:
            for sim, src, path in resonances[:3]:
                print(f"    🔗 内外共鸣[{sim:.3f}] {src}: {path[:60]}")
        else:
            print(f"    未检测到内外共鸣")

if __name__ == "__main__":
    main()
