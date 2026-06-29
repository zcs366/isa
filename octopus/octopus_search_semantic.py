#!/usr/bin/env python3
"""章鱼语义搜索 v0.1 — BGE-zh 嵌入通道（第六路·P2-1）

用法:
  python3 octopus_search_semantic.py <关键词>       # 语义搜索
  python3 octopus_search_semantic.py <关键词> --rerank   # 语义重排+关键词混合

模型: BAAI/bge-large-zh-v1.5（已下载）
"""
import sys, os, json, pickle
import numpy as np

MODEL_PATH = os.path.expanduser(
    "~/.hermes/hermes-agent/venv/lib/python3.12/site-packages/sentence_transformers"
)

# 缓存路径
EMBED_CACHE = os.path.expanduser("~/.hermes/octopus/semantic_embeddings.pkl")
DOC_INDEX = os.path.expanduser("~/projects/isa/octopus/tentacles")

_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(
            "/mnt/d/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/7999e1d3359715c523056ef9478215996d62a620",
            device="cpu")
    return _model

def build_embed_index():
    """构建文档嵌入索引（八触须文档 → 嵌入向量）"""
    import glob
    model = get_model()
    docs = []
    paths = []
    for root, dirs, files in os.walk(DOC_INDEX):
        for f in files:
            if f.endswith('.md'):
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', errors='replace') as fh:
                        text = fh.read()[:2000]
                    if text.strip():
                        docs.append(text)
                        paths.append(fp)
                except:
                    pass
    if not docs:
        return [], []
    
    embeddings = model.encode(docs, show_progress_bar=False, normalize_embeddings=True)
    return paths, embeddings

def search_semantic(query, top_k=10):
    """语义搜索：查询嵌入 → 余弦相似度排序"""
    import glob
    model = get_model()
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    
    # 加载或构建索引
    cache_path = EMBED_CACHE
    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            paths, embeddings = pickle.load(f)
    else:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        paths, embeddings = build_embed_index()
        with open(cache_path, 'wb') as f:
            pickle.dump((paths, embeddings), f)
    
    if not paths:
        return []
    
    # 相似度计算
    scores = np.dot(embeddings, q_emb)
    top_idx = np.argsort(scores)[-top_k:][::-1]
    
    results = []
    for i in top_idx:
        results.append((scores[i], paths[i]))
    
    return results

def main():
    if len(sys.argv) < 2:
        print("用法: python3 octopus_search_semantic.py <关键词>")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    rerank = "--rerank" in sys.argv
    
    print(f"🔮 章鱼语义搜索 (BGE-large-zh): {query}")
    print("=" * 50)
    
    results = search_semantic(query, top_k=10)
    
    if not results:
        print("无结果。")
        return
    
    for score, path in results:
        rel = os.path.relpath(path, DOC_INDEX) if DOC_INDEX in path else path
        print(f"  [{score:.4f}] {rel[:80]}")

if __name__ == "__main__":
    main()
