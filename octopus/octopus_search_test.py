#!/usr/bin/env python3
"""章鱼搜索质量测试集 v1.0 — P0-4

验证章鱼搜索在新优先级(八文档>RECALL>SESSION)下的质量。
每次修改后必须跑，确保未退化。

用法:
  python3 octopus_search_test.py           # 跑全部测试
  python3 octopus_search_test.py --summary # 只输出汇总
  python3 octopus_search_test.py --verbose # 详细输出

返回值: 0=全部通过, 1=有失败
"""
import sys, os, json, subprocess

OCTOPUS_DIR = os.path.expanduser("~/projects/isa/octopus")
TEST_QUERIES = [
    # (关键词, 期望来源, 最小命中数)
    ("章鱼", ["文档", "RECALL", "FILES"], 2),
    ("守恒律", ["文档", "RECALL", "FILES"], 2),
    ("八触须", ["文档", "RECALL", "SESSION"], 2),
    ("AGFT", ["文档"], 1),
    ("Δ胶囊", ["文档", "RECALL", "FILES"], 2),
    ("强制读取", ["文档", "RECALL"], 2),
    ("上下文管理", ["文档", "SESSION"], 2),
    ("审验之耻", ["文档"], 1),
    ("IAT", ["文档", "FILES", "SESSION"], 1),
    ("Tantivy", ["文档", "FILES"], 2),
]

PASS = 0
FAIL = 0
RESULTS = []

def run_test(query, expected_sources, min_hits):
    global PASS, FAIL
    try:
        r = subprocess.run(
            ["python3", "octopus_search.py", query],
            capture_output=True, text=True, timeout=30,
            cwd=OCTOPUS_DIR
        )
        output = r.stdout + r.stderr
        
        hit_sources = set()
        for src in expected_sources:
            # 文档 = 文档, FILES = FILES或文件, SESSION = SESSION, RECALL = RECALL, WEB = WEB
            alt = {"FILES": ["FILES", "文件"], "文档": ["文档"]}.get(src, [src])
            if any(a in output for a in alt):
                hit_sources.add(src)
        
        total_hits = output.count("[文档]") + output.count("[RECALL]") + output.count("msg#")
        
        missing = [s for s in expected_sources if s not in hit_sources]
        status = "✅" if (len(missing) == 0 and total_hits >= min_hits) else "❌"
        
        if status == "✅":
            PASS += 1
        else:
            FAIL += 1
        
        RESULTS.append((status, query, hit_sources, missing, total_hits, min_hits))
        return status
    except Exception as e:
        FAIL += 1
        RESULTS.append(("❌", query, set(), expected_sources, 0, min_hits))
        return "❌"

def main():
    global PASS, FAIL, RESULTS
    
    print("=" * 60)
    print("章鱼搜索质量测试集 v1.0")
    print(f"测试数: {len(TEST_QUERIES)} 查询")
    print(f"搜索策略: 八文档 > RECALL > SESSION > 其他")
    print("=" * 60)
    
    for query, sources, min_hits in TEST_QUERIES:
        run_test(query, sources, min_hits)
    
    print()
    print("=" * 60)
    print(f"结果: ✅ {PASS}/{len(TEST_QUERIES)} 通过, ❌ {FAIL}/{len(TEST_QUERIES)} 失败")
    print("=" * 60)
    
    for status, q, hits, missing, total, expected in RESULTS:
        if status == "❌":
            print(f"  ❌ {q}: 缺{missing}, 总{total}, 期望≥{expected}")
    
    # 输出汇总
    print()
    print("来源覆盖矩阵:")
    all_sources = set()
    for _, _, hits, _, _, _ in RESULTS:
        all_sources.update(hits)
    print(f"  覆盖来源: {', '.join(sorted(all_sources))}")
    
    return 0 if FAIL == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
