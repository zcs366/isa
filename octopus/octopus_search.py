#!/usr/bin/env python3
"""章鱼搜索引擎 v4.0 — Tantivy全文 + BGE语义 双引擎
用法: python3 octopus_search.py <关键词>

搜索通道（按优先级）:
  1. SESSION  ← 对话原文（state.db messages 表）
  2. RECALL   ← 事件摘要日志
  3. 文档     ← 触须文档.md
  4. BGE      ← BGE向量语义搜索（与Tantivy互补）
  5. FILES    ← 本地文件Tantivy索引
  6. WEB      ← 外部DuckDuckGo搜索
  7. Δ胶囊    ← Agent间共振记忆
  8. 文件名   ← find文件名搜索
"""
import sys, os, subprocess, json, time, re
import tantivy
import jieba
import numpy as _np_bge

OCTOPUS = os.path.expanduser("~/projects/isa/octopus")
INDEX_DIR = os.path.join(OCTOPUS, "tantivy_index")
BGE_INDEX_DIR = os.path.join(OCTOPUS, "bge_index")
HOME = os.path.expanduser("~")


# ── 查询分词 ──────────────────────────────────────────

def _segment_query(raw_query):
    """用 jieba 对查询词分词，并清理 Tantivy 查询语法不兼容字符"""
    query = raw_query.strip()
    while query and query[0] in '[](){}<>':
        query = query[1:]
    query = re.sub(r'(\b[A-Za-z0-9_]+):', r'\1 ', query)
    query = re.sub(r'[@#$]', ' ', query)
    query = re.sub(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE00-\uFE0F]', '', query)
    query = re.sub(r'[·。，、！？：；""''【】《》（）—…•●○◎※→←↑↓★☆]', ' ', query)
    query = query.rstrip(']}>')
    if len(query) > 80 and any(kw in query for kw in ["Background", "process", "IMPORTANT", "Error"]):
        chinese = re.findall(r'[\u4e00-\u9fff]{2,}', query)
        if chinese:
            query = " ".join(chinese[:5])
        else:
            query = query[:40]
    query = " ".join(word for word in query.split()
                     if not (word[0].isdigit() and len(word) > 1 and word[1] in '.):;!?'))
    segmented = " ".join(jieba.cut(query))
    segmented = re.sub(r'\s+([-–—])\s+', r'\1', segmented)
    tokens = [t for t in segmented.split() if not re.match(r'^[，。、；：？！\u201c\u201d\u2018\u2019【】《》（）—…·/\\\s]+$', t)]
    return " ".join(tokens) if tokens else segmented


# ─── 通道1: SESSION 搜索 ─────────────────────────────

def _build_sessions_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("session_id", stored=True)
    builder.add_text_field("role", stored=True)
    builder.add_text_field("body", stored=True)
    builder.add_integer_field("ts", stored=True)
    return builder.build()


def search_sessions(query_str, limit=10):
    results = []
    sessions_path = os.path.join(INDEX_DIR, "sessions")
    if not os.path.exists(sessions_path):
        return results
    try:
        schema = _build_sessions_schema()
        index = tantivy.Index(schema, path=sessions_path)
        index.reload()
        searcher = index.searcher()
        seg_query = _segment_query(query_str)
        parsed = index.parse_query(seg_query, ["body"])
        hits = searcher.search(parsed, limit=limit)
        for score, doc_addr in hits.hits:
            doc = searcher.doc(doc_addr)
            mid = doc["id"][0] if doc["id"] else ""
            session_id = doc["session_id"][0] if doc["session_id"] else ""
            role = doc["role"][0] if doc["role"] else ""
            body = doc["body"][0][:200] if doc["body"] else ""
            label = f"[SESSION] msg#{mid} ({role}) [{session_id[:12]}...]"
            results.append(("SESSION", label, score, body, session_id))
    except Exception as e:
        results.append(("SESSION", f"error: {e}", 0, "", ""))
    return results


# ─── 通道2: RECALL 搜索 ──────────────────────────────

def _build_recall_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("body", stored=True)
    return builder.build()


def search_recall(query_str, limit=10):
    results = []
    recall_path = os.path.join(INDEX_DIR, "recall")
    if not os.path.exists(recall_path):
        return results
    try:
        schema = _build_recall_schema()
        index = tantivy.Index(schema, path=recall_path)
        index.reload()
        searcher = index.searcher()
        seg_query = _segment_query(query_str)
        parsed = index.parse_query(seg_query, ["body"])
        hits = searcher.search(parsed, limit=limit)
        for score, doc_addr in hits.hits:
            doc = searcher.doc(doc_addr)
            doc_id = doc["id"][0]
            body = doc["body"][0][:200] if doc["body"] else ""
            results.append(("[RECALL]", doc_id, score, body))
    except Exception as e:
        results.append(("[RECALL]", f"error: {e}", 0, ""))
    return results


# ─── 通道3: 文档搜索 ──────────────────────────────────

def _build_docs_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("title", stored=True)
    builder.add_text_field("tentacle", stored=True)
    builder.add_text_field("body", stored=True)
    return builder.build()


def search_docs(query_str, limit=10):
    results = []
    docs_path = os.path.join(INDEX_DIR, "docs")
    if not os.path.exists(docs_path):
        return results
    try:
        schema = _build_docs_schema()
        index = tantivy.Index(schema, path=docs_path)
        index.reload()
        searcher = index.searcher()
        parsed = index.parse_query(query_str, ["body", "title"])
        hits = searcher.search(parsed, limit=limit)
        for score, doc_addr in hits.hits:
            doc = searcher.doc(doc_addr)
            filepath = doc["id"][0] if doc["id"] else ""
            title = doc["title"][0] if doc["title"] else ""
            tentacle = doc["tentacle"][0] if doc["tentacle"] else ""
            body = doc["body"][0][:200] if doc["body"] else ""
            label = f"[文档/{tentacle}] {title}" if tentacle else title
            results.append(("[文档]", label, score, body, filepath))
    except Exception as e:
        results.append(("[文档]", f"error: {e}", 0, "", ""))
    return results


# ─── 通道4: 本地文件搜索 ──────────────────────────────

def _build_files_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("name", stored=True)
    builder.add_text_field("ext", stored=True)
    builder.add_text_field("fmt", stored=True)
    builder.add_text_field("body", stored=True)
    builder.add_integer_field("size", stored=True)
    builder.add_integer_field("mtime", stored=True)
    return builder.build()


def search_files(query_str, limit=8):
    results = []
    files_path = os.path.join(INDEX_DIR, "files")
    if not os.path.exists(files_path):
        return results
    try:
        schema = _build_files_schema()
        index = tantivy.Index(schema, path=files_path)
        index.reload()
        searcher = index.searcher()
        parsed = index.parse_query(query_str, ["body", "name", "id"])
        hits = searcher.search(parsed, limit=limit)
        for score, doc_addr in hits.hits:
            doc = searcher.doc(doc_addr)
            fp = doc["id"][0] if doc["id"] else ""
            name = doc["name"][0] if doc["name"] else ""
            fmt = doc["fmt"][0] if doc["fmt"] else ""
            ext = doc["ext"][0] if doc["ext"] else ""
            body = doc["body"][0][:120] if doc["body"] else ""
            results.append(("[FILES]", fp, score, body, fmt, ext))
    except Exception as e:
        results.append(("[FILES]", f"error: {e}", 0, "", "", ""))
    return results


# ─── 通道5: Δ胶囊共振搜索 ─────────────────────────────

def search_resonance(query_str, limit=10):
    results = []
    res_path = os.path.join(INDEX_DIR, "resonance")
    if not os.path.exists(res_path):
        return results
    try:
        builder = tantivy.SchemaBuilder()
        builder.add_text_field("id", stored=True)
        builder.add_text_field("source", stored=True)
        builder.add_text_field("target", stored=True)
        builder.add_text_field("intent", stored=True)
        builder.add_text_field("body", stored=True)
        schema = builder.build()
        index = tantivy.Index(schema, path=res_path)
        index.reload()
        searcher = index.searcher()
        parsed = index.parse_query(query_str, ["body", "intent"])
        hits = searcher.search(parsed, limit=limit)
        for score, doc_addr in hits.hits:
            doc = searcher.doc(doc_addr)
            src = doc["source"][0][:16] if doc["source"] else "?"
            intent = doc["intent"][0] if doc["intent"] else "?"
            body = doc["body"][0][:200] if doc["body"] else ""
            results.append(("[Δ胶囊]", f"from={src} intent={intent}", score, body))
    except Exception:
        pass
    return results


# ─── 通道6: 外部 Web 搜索 ─────────────────────────────

def search_web(query_str, limit=5):
    results = []
    try:
        script = os.path.join(os.path.dirname(__file__), "octopus_web_search.py")
        r = subprocess.run(
            ["python3", script, query_str],
            capture_output=True, text=True, timeout=12
        )
        if r.returncode == 0:
            for line in r.stdout.split("\n"):
                if line.startswith("  [WEB] "):
                    title = line[8:].strip()
                    results.append(("[WEB]", title, "", ""))
        if not results:
            import urllib.request as _ur, urllib.parse as _up
            data = _up.urlencode({"q": query_str}).encode()
            req = _ur.Request(
                "https://html.duckduckgo.com/html/",
                data=data,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with _ur.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            for m in re.findall(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                href, title_html = m
                title = re.sub(r'<[^>]+>', "", title_html).strip()
                if title and not href.startswith("javascript"):
                    if "/redirect?*uddg=" in href:
                        uddg = re.search(r'uddg=([^&]+)', href)
                        if uddg:
                            href = _up.unquote(uddg.group(1))
                    results.append(("[WEB]", title, href, ""))
                    if len(results) >= limit:
                        break
    except Exception as e:
        results.append(("[WEB]", f"web search error: {e}", "", ""))
    return results


# ─── 通道7: 文件名搜索 ────────────────────────────────

def search_files_find(query, limit=10):
    results = []
    search_dirs = [
        os.path.join(HOME, "projects"),
        os.path.join(HOME, ".hermes/jiak"),
    ]
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        try:
            r = subprocess.run(
                ["find", d, "-name", f"*{query}*", "-type", "f", "-maxdepth", "4"],
                capture_output=True, text=True, timeout=5
            )
            for f in r.stdout.strip().split("\n")[:limit]:
                if f:
                    results.append(("[文件]", f, 0, ""))
        except Exception:
            pass
    return results


# ─── 通道8: BGE 语义搜索 ──────────────────────────────

_bge_model = None
_bge_vectors = None
_bge_chunks = None


def _bge_load():
    """懒加载BGE向量索引"""
    global _bge_model, _bge_vectors, _bge_chunks
    if _bge_vectors is not None and _bge_chunks is not None:
        return True
    vectors_path = os.path.join(BGE_INDEX_DIR, "vectors.npy")
    chunks_path = os.path.join(BGE_INDEX_DIR, "chunks.jsonl")
    if not os.path.exists(vectors_path) or not os.path.exists(chunks_path):
        return False
    try:
        _bge_vectors = _np_bge.load(vectors_path)
        if _bge_vectors.shape[0] == 0:
            return False
        with open(chunks_path, "r") as f:
            _bge_chunks = [json.loads(line) for line in f if line.strip()]
        from sentence_transformers import SentenceTransformer
        model_path = "/mnt/d/models/bge-large-zh-v1.5"
        _bge_model = SentenceTransformer(model_path, device="cpu")
        return True
    except Exception as e:
        print(f"[BGE] 加载失败: {e}")
        return False


def search_bge(query_str, limit=8, min_score=0.25):
    """BGE语义搜索 — 与Tantivy互补的向量检索通道"""
    results = []
    if not _bge_load():
        return results
    try:
        q_vec = _bge_model.encode([query_str], normalize_embeddings=True)[0]
        scores = _bge_vectors @ q_vec
        top_indices = _np_bge.argsort(scores)[::-1][:limit]
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score:
                break
            chunk = _bge_chunks[idx] if idx < len(_bge_chunks) else {}
            label = f"[BGE/{chunk.get('type','?')}] {chunk.get('title','?')} (score={score:.3f})"
            body = chunk.get("text", "")[:200]
            results.append(("BGE", label, score, body, chunk.get("path", "")))
    except Exception as e:
        results.append(("BGE", f"error: {e}", 0, "", ""))
    return results


# ─── 通道缓存 ─────────────────────────────────────────

_CHANNEL_CACHE = {}
_MAX_CACHE_PER_CHANNEL = 100


def _cache_key(query: str) -> str:
    return " ".join(sorted(set(_segment_query(query).split())))


def _channel_cache_get(channel: str, query: str):
    key = _cache_key(query)
    entries = _CHANNEL_CACHE.get(channel, [])
    now = time.time()
    for k, results, expiry in entries:
        if k == key and now < expiry:
            return results
    return None


def _channel_cache_set(channel: str, query: str, results: list):
    key = _cache_key(query)
    expiry = time.time() + 300
    entries = _CHANNEL_CACHE.get(channel, [])
    for i, (k, _, _) in enumerate(entries):
        if k == key:
            entries[i] = (key, results, expiry)
            break
    else:
        entries.append((key, results, expiry))
    if len(entries) > _MAX_CACHE_PER_CHANNEL:
        entries = entries[-_MAX_CACHE_PER_CHANNEL:]
    _CHANNEL_CACHE[channel] = entries


def _cache_triple(src, label, snippet, filepath=""):
    return (src, label, snippet, filepath)


# ─── 两阶段搜索展开 ──────────────────────────────────

def search_expand(query: str, raw_query: str):
    """两阶段搜索：先本地4路（含BGE语义）→ 置信不足再外扩"""
    all_results = []
    local_result_count = 0
    expanded = False

    # 阶段1: 本地通道（Tantivy + BGE 双引擎）
    for ch_name, ch_fn, ch_args, body_idx in [
        ("文档", search_docs, (query,), 3),
        ("RECALL", search_recall, (query,), 3),
        ("SESSION", search_sessions, (query,), 3),
        ("BGE", search_bge, (query,), 3),
    ]:
        cached = _channel_cache_get(ch_name, query)
        if cached is not None:
            results = cached
        else:
            results = ch_fn(*ch_args)
            _channel_cache_set(ch_name, query, results)
        for item in results:
            label = str(item[1]) if len(item) > 1 else ""
            snippet = str(item[body_idx])[:200] if len(item) > body_idx else ""
            fp = str(item[4]) if ch_name in ("文档", "BGE") and len(item) > 4 else ""
            all_results.append(_cache_triple(f"[{ch_name}]", label, snippet, fp))
        local_result_count += len(results)

    # 置信度判断
    query_terms = set(_segment_query(query).split())
    unique_terms_found = set()
    for item in all_results:
        snippet = item[2] if len(item) > 2 else ""
        for term in query_terms:
            is_ascii_single = all(ord(c) < 128 for c in term) and len(term) == 1
            if term in snippet and not is_ascii_single:
                unique_terms_found.add(term)
    good_enough = len(unique_terms_found) >= min(2, len(query_terms)) and local_result_count >= 3

    if good_enough:
        return all_results, False

    expanded = True

    # 阶段2: 展开到外部通道
    for ch_name, ch_fn, ch_args, body_idx in [
        ("FILES", search_files, (query,), 3),
        ("WEB", search_web, (raw_query,), 3),
        ("Δ胶囊", search_resonance, (query,), 3),
        ("文件", search_files_find, (query,), 3),
    ]:
        cached = _channel_cache_get(ch_name, query)
        if cached is not None:
            results = cached
        else:
            results = ch_fn(*ch_args)
            _channel_cache_set(ch_name, query, results)
        for item in results:
            label = str(item[1]) if len(item) > 1 else ""
            snippet = str(item[body_idx])[:200] if len(item) > body_idx else ""
            all_results.append(_cache_triple(f"[{ch_name}]", label, snippet))
        if results:
            break

    return all_results, True


# ─── IKO富化层 ────────────────────────────────────────

def _iko_enrich_results(all_results: list) -> list:
    """搜索结果的IKO后处理：为文档/FILES结果附加会话关联"""
    from octopus_file_session_link import find_session_refs as _find_refs
    enriched = list(all_results)
    seen_sessions = set()
    for item in all_results:
        src = item[0]
        if not src.startswith("[文档]"):
            continue
        fp = item[3] if len(item) > 3 and item[3] else ""
        if not fp or not os.path.exists(fp):
            continue
        try:
            refs = _find_refs(fp)
        except Exception:
            continue
        for ref in refs[:3]:
            sid = ref.get("session_id", "")
            if sid in seen_sessions or not sid:
                continue
            seen_sessions.add(sid)
            enriched.append((
                "[IKO]",
                f"💬 {ref.get('title', sid[:16])[:40]} ({ref.get('role', '?')})",
                f"[{ref.get('time', '?')}] {ref.get('preview', '')[:80]}",
                ""
            ))
    return enriched


# ─── 主函数 ───────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("用法: python3 octopus_search.py <关键词>")
        sys.exit(1)

    raw_query = sys.argv[1]
    query = _segment_query(raw_query)
    print(f"🐙 章鱼搜索 v4.0 (Tantivy+BGE双引擎): {raw_query}")
    print(f"   分词查询: {query}")
    print("=" * 50)

    all_results, expanded = search_expand(query, raw_query)
    enriched_results = _iko_enrich_results(all_results)

    if not all_results:
        print("无结果。")
        return

    from collections import Counter
    src_type_counts = Counter()
    for item in enriched_results:
        source = item[0]
        st = source.split()[0] if " " in source else source
        st = st.strip("[]")
        src_type_counts[st] += 1

    display_slots = {}
    for src_type in src_type_counts:
        display_slots[src_type] = max(2, min(6, src_type_counts[src_type]))

    source_priority = {"文档": 0, "IKO": 1, "BGE": 1, "RECALL": 2, "SESSION": 3, "FILES": 4, "文件": 5, "WEB": 6}
    enriched_results.sort(key=lambda x: source_priority.get(
        x[0].split()[0].strip("[]") if " " in x[0] else x[0].strip("[]"), 99))

    valid_sources = {"SESSION", "RECALL", "文档", "FILES", "文件", "WEB", "IKO", "BGE", "Δ胶囊"}
    seen = set()
    count = 0
    for item in enriched_results:
        source = item[0]
        path_or_label = item[1] if len(item) > 1 else ""
        snippet = item[2] if len(item) > 2 else ""
        st = source.split()[0] if " " in source else source
        st = st.strip("[]")
        if st not in valid_sources:
            continue
        if display_slots.get(st, 0) <= 0:
            continue
        key = f"{source}:{path_or_label}"
        if key in seen:
            continue
        seen.add(key)
        display_slots[st] -= 1
        count += 1
        print(f"\n  {source} {path_or_label}")
        if snippet:
            print(f"  {snippet[:200]}")
        if count >= 25:
            break

    print(f"\n共 {len(all_results)} 条原始结果，IKO富化后 {len(enriched_results)} 条，去重展示 {count} 条。"
          f" {'✅ 本地已覆盖，未展开到外部' if not expanded else '🌐 已展开到外部通道'}")


if __name__ == "__main__":
    main()
