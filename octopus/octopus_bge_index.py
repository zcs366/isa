#!/usr/bin/env python3
"""章鱼搜索引擎 — BGE向量语义检索通道 (v1.0)

三层架构中的语义检索层：
  SQLite (存储+事务) + Tantivy (全文检索) + BGE (语义检索)

用法:
  # 建索引（增量，只处理新文件）
  python3 octopus_bge_index.py --build

  # 搜索
  python3 octopus_bge_index.py "守恒律"

  # 作为模块导入
  from octopus_bge_index import bge_search, bge_build_index
"""
import os, sys, json, time, hashlib, struct, pickle
import numpy as np

OCTOPUS = os.path.expanduser("~/projects/isa/octopus")
INDEX_DIR = os.path.join(OCTOPUS, "bge_index")
MODEL_PATH = "/mnt/d/models/bge-large-zh-v1.5"
BATCH_SIZE = 32
MAX_SEQ_LEN = 512

# ── 索引结构 ──────────────────────────────────────────
# bge_index/
#   meta.json        — 文档ID→路径映射
#   vectors.npy      — N×1024 float32向量矩阵
#   chunks.jsonl     — 每个向量对应的chunk文本+元数据

_model = None

def _get_model():
    """懒加载BGE模型（首次调用~3s，后续~0ms）"""
    global _model
    if _model is not None:
        return _model
    from sentence_transformers import SentenceTransformer
    print(f"[BGE] 加载模型: {MODEL_PATH}")
    t0 = time.time()
    _model = SentenceTransformer(MODEL_PATH, device="cpu")
    print(f"[BGE] 模型加载完成 ({time.time()-t0:.1f}s), dim={_model.get_sentence_embedding_dimension()}")
    return _model


def _chunk_text(text: str, max_chars: int = 500, overlap: int = 100) -> list[str]:
    """将长文本切分为固定大小的chunk（带重叠）"""
    if len(text) <= max_chars:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
        if start + overlap >= len(text):
            break
    return chunks


def _collect_documents() -> list[dict]:
    """收集所有待索引的文档（八触须文档 + RECALL + session摘要）"""
    docs = []
    home = os.path.expanduser("~")

    # 1. 八触须文档
    tentacles_dir = os.path.join(OCTOPUS, "tentacles")
    for root, dirs, files in os.walk(tentacles_dir):
        for f in files:
            if f.endswith(".md"):
                fp = os.path.join(root, f)
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    # 从路径提取触须类型
                    rel = os.path.relpath(fp, tentacles_dir)
                    tentacle = rel.split(os.sep)[0] if os.sep in rel else "unknown"
                    docs.append({
                        "id": f"tentacle:{fp}",
                        "path": fp,
                        "type": "tentacle",
                        "tentacle": tentacle,
                        "title": f.replace(".md", ""),
                        "content": content,
                        "mtime": os.path.getmtime(fp),
                    })
                except Exception:
                    pass

    # 2. RECALL.jsonl
    recall_path = os.path.join(home, ".hermes/jiak/RECALL.jsonl")
    if os.path.exists(recall_path):
        try:
            with open(recall_path, "r", encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        content = entry.get("content", "") or entry.get("summary_short", "")
                        if content:
                            docs.append({
                                "id": f"recall:{i}",
                                "path": recall_path,
                                "type": "recall",
                                "tentacle": "recall",
                                "title": f"RECALL#{i}",
                                "content": content,
                                "mtime": entry.get("ts", ""),
                            })
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    # 3. jiak卡片
    cards_dir = os.path.join(home, ".hermes/jiak/cards")
    if os.path.exists(cards_dir):
        for f in os.listdir(cards_dir):
            if f.endswith(".json"):
                fp = os.path.join(cards_dir, f)
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        card = json.load(fh)
                    content = card.get("summary", "") or card.get("description", "")
                    # 也包含最近的notes
                    notes = card.get("notes", [])
                    if notes:
                        recent_notes = [n[1] for n in notes[-10:] if isinstance(n, list) and len(n) > 1]
                        content += "\n" + "\n".join(recent_notes)
                    if content.strip():
                        docs.append({
                            "id": f"jiak:{f}",
                            "path": fp,
                            "type": "jiak",
                            "tentacle": "jiak",
                            "title": f.replace(".json", ""),
                            "content": content.strip(),
                            "mtime": os.path.getmtime(fp),
                        })
                except Exception:
                    pass

    # 4. output目录中的分析/备忘录/技术文档
    output_base = os.path.expanduser("~/hermes/output")
    for search_dir in [
        os.path.join(output_base, "极大"),
        os.path.join(output_base, "大"),
        os.path.join(output_base, "doc"),
    ]:
        if not os.path.exists(search_dir):
            continue
        for f in os.listdir(search_dir):
            if f.endswith(".md"):
                fp = os.path.join(search_dir, f)
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        content = fh.read(20000)  # 限制读取大小
                    docs.append({
                        "id": f"output:{fp}",
                        "path": fp,
                        "type": "output",
                        "tentacle": "output",
                        "title": f.replace(".md", ""),
                        "content": content,
                        "mtime": os.path.getmtime(fp),
                    })
                except Exception:
                    pass

    return docs


def bge_build_index(force: bool = False):
    """构建BGE向量索引（增量：只处理新增/修改的文件）"""
    os.makedirs(INDEX_DIR, exist_ok=True)
    meta_path = os.path.join(INDEX_DIR, "meta.json")
    vectors_path = os.path.join(INDEX_DIR, "vectors.npy")
    chunks_path = os.path.join(INDEX_DIR, "chunks.jsonl")

    # 加载现有索引
    existing_meta = {}
    existing_vectors = None
    existing_chunks = []
    if os.path.exists(meta_path) and not force:
        with open(meta_path, "r") as f:
            existing_meta = json.load(f)
        if os.path.exists(vectors_path):
            existing_vectors = np.load(vectors_path)
        if os.path.exists(chunks_path):
            with open(chunks_path, "r") as f:
                existing_chunks = [json.loads(line) for line in f if line.strip()]

    # 收集文档
    docs = _collect_documents()
    print(f"[BGE] 收集到 {len(docs)} 个文档")

    # 找出需要更新的文档
    to_update = []
    for doc in docs:
        doc_id = doc["id"]
        current_mtime = doc["mtime"]
        if doc_id in existing_meta:
            old_mtime = existing_meta[doc_id].get("mtime", 0)
            if current_mtime <= old_mtime:
                continue
        to_update.append(doc)

    if not to_update and not force:
        print(f"[BGE] 索引已是最新 ({len(existing_meta)} 文档, {len(existing_chunks)} chunks)")
        return

    if force:
        to_update = docs
        existing_meta = {}
        existing_vectors = None
        existing_chunks = []

    print(f"[BGE] 需要索引 {len(to_update)} 个文档")

    # 加载模型
    model = _get_model()

    # 对新文档做chunk+embed
    new_chunks = []
    new_vectors = []
    for doc in to_update:
        chunks = _chunk_text(doc["content"])
        for i, chunk in enumerate(chunks):
            new_chunks.append({
                "doc_id": doc["id"],
                "path": doc["path"],
                "type": doc["type"],
                "tentacle": doc["tentacle"],
                "title": doc["title"],
                "chunk_idx": i,
                "text": chunk,
            })
        if chunks:
            embeddings = model.encode(chunks, batch_size=BATCH_SIZE,
                                      show_progress_bar=len(chunks) > 50,
                                      normalize_embeddings=True)
            new_vectors.append(embeddings)
            existing_meta[doc["id"]] = {
                "path": doc["path"],
                "type": doc["type"],
                "mtime": doc["mtime"],
                "chunk_count": len(chunks),
                "chunk_start": len(existing_chunks),
            }
        existing_chunks.extend(new_chunks[-len(chunks):] if chunks else [])
        new_chunks = []  # 重置

    # 合并向量
    if new_vectors:
        new_vecs = np.concatenate(new_vectors, axis=0)
        if existing_vectors is not None and not force:
            all_vectors = np.vstack([existing_vectors, new_vecs])
        else:
            all_vectors = new_vecs
    else:
        all_vectors = existing_vectors if existing_vectors is not None else np.empty((0, 1024), dtype=np.float32)

    # 保存
    with open(meta_path, "w") as f:
        json.dump(existing_meta, f, ensure_ascii=False, indent=2)
    np.save(vectors_path, all_vectors)
    with open(chunks_path, "w") as f:
        for chunk in existing_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"[BGE] 索引构建完成: {len(existing_meta)} 文档, {len(existing_chunks)} chunks, {all_vectors.shape[0]} 向量")


def bge_search(query: str, limit: int = 10, min_score: float = 0.3) -> list[dict]:
    """BGE语义搜索 — 返回最相关的chunks"""
    vectors_path = os.path.join(INDEX_DIR, "vectors.npy")
    chunks_path = os.path.join(INDEX_DIR, "chunks.jsonl")

    if not os.path.exists(vectors_path) or not os.path.exists(chunks_path):
        return []

    # 加载索引
    vectors = np.load(vectors_path)
    if vectors.shape[0] == 0:
        return []

    with open(chunks_path, "r") as f:
        chunks = [json.loads(line) for line in f if line.strip()]

    # 编码查询
    model = _get_model()
    q_vec = model.encode([query], normalize_embeddings=True)[0]  # (1024,)

    # 余弦相似度（已归一化，点积=余弦）
    scores = vectors @ q_vec  # (N,)

    # Top-K
    top_indices = np.argsort(scores)[::-1][:limit]
    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score < min_score:
            break
        chunk = chunks[idx] if idx < len(chunks) else {}
        results.append({
            "score": round(score, 4),
            "text": chunk.get("text", "")[:300],
            "doc_id": chunk.get("doc_id", ""),
            "path": chunk.get("path", ""),
            "type": chunk.get("type", ""),
            "tentacle": chunk.get("tentacle", ""),
            "title": chunk.get("title", ""),
        })

    return results


def bge_search_formatted(query: str, limit: int = 10) -> list[tuple]:
    """格式化搜索结果，与章鱼其他通道输出格式兼容"""
    results = bge_search(query, limit=limit)
    formatted = []
    for r in results:
        label = f"[BGE/{r['type']}] {r['title']} (score={r['score']})"
        formatted.append(("BGE", label, r["score"], r["text"][:200], r["path"]))
    return formatted


# ── CLI ──────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 octopus_bge_index.py [--build] <查询词>")
        sys.exit(1)

    if sys.argv[1] == "--build":
        force = "--force" in sys.argv
        bge_build_index(force=force)
    else:
        query = " ".join(sys.argv[1:])
        results = bge_search(query)
        print(f"🔍 BGE语义搜索: {query}")
        print(f"   结果数: {len(results)}")
        print("=" * 60)
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['type']}] {r['title']} (score={r['score']})")
            print(f"   path: {r['path']}")
            print(f"   text: {r['text'][:150]}...")
