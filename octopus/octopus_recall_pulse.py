#!/usr/bin/env python3
"""章鱼回忆脉胳引擎 v0.1 — P2-4

功能: 搜索结果 + 过往经验 = 回忆脉胳
不仅仅是搜到结果——而是搜到结果后解释'这个结果和之前遇到的那个问题有什么关系'

用法:
  python3 octopus_recall_pulse.py <关键词>     # 搜索+脉胳
  python3 octopus_recall_pulse.py <关键词> --json  # JSON输出
"""
import sys, os, json, glob, subprocess
import numpy as np

HOME = os.path.expanduser("~")
OCTOPUS = os.path.expanduser("~/projects/isa/octopus")
TENTACLES = os.path.join(OCTOPUS, "tentacles")
EMBED_CACHE = os.path.expanduser("~/.hermes/octopus/semantic_embeddings.pkl")

_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(
            "/mnt/d/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/7999e1d3359715c523056ef9478215996d62a620",
            device="cpu")
    return _model

def load_embed_index():
    """加载或构建文档嵌入索引"""
    if os.path.exists(EMBED_CACHE):
        with open(EMBED_CACHE, 'rb') as f:
            import pickle
            return pickle.load(f)
    return [], []

def search_internal_docs(query):
    """内部文档搜索"""
    docs = []
    for root, dirs, files in os.walk(TENTACLES):
        for f in files:
            if f.endswith('.md'):
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', errors='replace') as fh:
                        content = fh.read()
                    if query in content:
                        docs.append((fp, content[:2000]))
                except:
                    pass
    return docs[:10]

def find_pulse(query):
    """生成回忆脉胳
    
    三轮递进:
    L2-1: 当前搜索结果与最相似的历史文档之间的语义距离
    L2-2: 该历史文档的决策因果链(lesson/memo中的'为什么'段落)
    L2-3: 该历史文档引发的其他相关文档(图传播)
    """
    model = get_model()
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    
    # L2-1: 语义搜索
    docs = search_internal_docs(query)
    if not docs:
        return []
    
    doc_embs = model.encode([d[1][:500] for d in docs], normalize_embeddings=True)
    sims = [float(np.dot(q_emb, de)) for de in doc_embs]
    
    # 按相似度排序
    ranked = sorted(zip(sims, docs), key=lambda x: -x[0])
    pulses = []
    
    for sim, (fp, content) in ranked[:5]:
        if sim < 0.3:
            continue
        
        rel_path = os.path.relpath(fp, TENTACLES)
        base = os.path.basename(fp)
        
        # L2-2: 提取关键句(含'为什么'/'因为'/'于是'的段落)
        key_lines = ""
        for line in content.split("\n"):
            if any(kw in line for kw in ["为什么", "因为", "于是", "结论", "决策", "选择"]):
                key_lines += line.strip()[:100] + "\n"
        
        # L2-3: 同一触须目录下的关联文件
        related = []
        base_dir = os.path.dirname(fp)
        if os.path.exists(base_dir):
            for f in os.listdir(base_dir):
                if f != os.path.basename(fp) and f.endswith('.md'):
                    related.append(f)
        
        pulses.append({
            "sim": round(sim, 3),
            "path": rel_path,
            "filename": base,
            "key_lines": key_lines[:200] if key_lines else content[:200],
            "related": related[:3]
        })
    
    return pulses

def main():
    if len(sys.argv) < 2:
        print("用法: python3 octopus_recall_pulse.py <关键词>")
        sys.exit(1)
    
    query = " ".join([a for a in sys.argv[1:] if not a.startswith("--")])
    json_output = "--json" in sys.argv
    
    pulses = find_pulse(query)
    
    if not pulses:
        print(f"📡 章鱼回忆脉胳: {query}")
        print("=" * 50)
        print("未找到有意义的回忆脉胳（语义相似度<0.3或无历史文档）")
        return
    
    if json_output:
        print(json.dumps(pulses, indent=2, ensure_ascii=False))
        return
    
    print(f"📡 章鱼回忆脉胳: {query}")
    print("=" * 50)
    
    for p in pulses[:3]:
        print(f"\n  🔗 脉胳[{p['sim']:.3f}] {p['filename'][:60]}")
        print(f"    📂 {p['path'][:70]}")
        print(f"    💡 {p['key_lines'][:100]}")
        if p['related']:
            print(f"    📎 关联: {', '.join(p['related'][:3])}")

if __name__ == "__main__":
    main()
