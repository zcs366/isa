#!/usr/bin/env python3
"""章鱼语义搜索 v0.2 — BGE-large-zh双模型(P2-1升级+v5.0)
与v0.1接口兼容，支持large/small自动切换
"""
import sys, os, pickle, glob, time
import numpy as np

HOME = os.path.expanduser("~")
TENTACLES = os.path.expanduser("~/projects/isa/octopus/tentacles")
EMBED_CACHE_SM = os.path.expanduser("~/.hermes/octopus/semantic_embeddings_small.pkl")
EMBED_CACHE_LG = os.path.expanduser("~/.hermes/octopus/semantic_embeddings_large.pkl")

LG_PATHS = [
    "/mnt/d/.cache/huggingface/hub/models--BAAI--bge-large-zh-v1.5/snapshots",
    "/mnt/d/models/models--BAAI--bge-large-zh-v1.5/snapshots",
]
SM_PATH = "/mnt/d/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/7999e1d3359715c523056ef9478215996d62a620"

def find_large_path():
    for base in LG_PATHS:
        if os.path.exists(base):
            snaps = os.listdir(base)
            if snaps:
                fp = os.path.join(base, snaps[0])
                if os.path.exists(os.path.join(fp, "model.safetensors")):
                    return fp
    return None

_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        lg = find_large_path()
        if lg:
            print("🔮 使用 BGE-large-zh", file=sys.stderr)
            _model = SentenceTransformer(lg, device="cpu")
        else:
            print("🔮 使用 BGE-small-zh (large未下载)", file=sys.stderr)
            _model = SentenceTransformer(SM_PATH, device="cpu")
    return _model

def search_semantic(query, top_k=10):
    model = get_model()
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    cache = EMBED_CACHE_LG if find_large_path() else EMBED_CACHE_SM
    
    if os.path.exists(cache):
        with open(cache, 'rb') as f:
            paths, embeddings = pickle.load(f)
    else:
        paths, texts = [], []
        for root, dirs, files in os.walk(TENTACLES):
            for f in files:
                if f.endswith('.md'):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, 'r', errors='replace') as fh:
                            t = fh.read()[:2000]
                        if t.strip():
                            paths.append(fp)
                            texts.append(t)
                    except: pass
        if not texts:
            return []
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, 'wb') as f:
            pickle.dump((paths, embeddings), f)
    
    scores = np.dot(embeddings, q_emb)
    top = np.argsort(scores)[-top_k:][::-1]
    return [(scores[i], paths[i]) for i in top]

def main():
    q = " ".join([a for a in sys.argv[1:] if not a.startswith("--")])
    if not q:
        print("用法: python3 octopus_search_semantic_v5.py <关键词>")
        sys.exit(1)
    print(f"🔮 章鱼语义搜索 v5.0: {q}")
    print("=" * 50)
    for score, path in search_semantic(q):
        rel = os.path.relpath(path, TENTACLES) if TENTACLES in path else path
        print(f"  [{score:.4f}] {rel[:80]}")

if __name__ == "__main__":
    main()
