#!/usr/bin/env python3
"""cross_format_detector.py — 跨格式模式匹配 (M2)
同一时段产生的文档+代码+脚本，检测同主题关联。

用法:
  python3 cross_format_detector.py                      # 全量扫描
  python3 cross_format_detector.py --time-window 60     # 60分钟窗口
"""
import json, os, sys, re, glob
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

OUTPUT_DIR = Path.home() / "hermes" / "output" / "极大"
SCRIPTS_DIR = Path.home() / "hermes" / "output" / "scripts"
EMERGENCE_DIR = Path.home() / "projects" / "isa" / "octopus" / "emergence"
JIAK_DIR = Path.home() / ".hermes" / "jiak"
OUTPUT_PATH = EMERGENCE_DIR / "cross_format_results.json"


def extract_keywords(text: str) -> set[str]:
    """提取文本中的关键词（中英文2字以上）"""
    kws = set()
    for token in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z_]{4,}', text):
        # 过滤停用词
        if token.lower() in ("import", "from", "class", "def", "return", "self", "true", "false", "none", "the", "this", "that", "with", "for", "and"):
            continue
        kws.add(token.lower()[:30])
    return kws


def get_file_time(filepath: Path) -> datetime | None:
    """获取文件修改时间"""
    try:
        mtime = filepath.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except Exception:
        return None


def collect_files() -> list[dict]:
    """收集所有可检测的文件"""
    files = []

    # 递归扫描 output/ 下所有 .md（覆盖全部子目录）
    for f in sorted(Path.home().glob("hermes/output/**/*.md")):
        if f.name.startswith("_") or "INDEX" in f.name:
            continue
        ft = get_file_time(f)
        if ft:
            files.append({"path": str(f), "name": f.name, "type": "doc", "time": ft})

    # output/scripts下的脚本
    for f in sorted(SCRIPTS_DIR.glob("*")):
        if not f.is_file():
            continue
        ft = get_file_time(f)
        if ft:
            files.append({"path": str(f), "name": f.name, "type": "script", "time": ft})

    return files


def detect_cross_format(files: list[dict], time_window_minutes: int = 30) -> list[dict]:
    """检测跨格式关联"""
    results = []

    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            f1, f2 = files[i], files[j]

            # 同类型不比较
            if f1["type"] == f2["type"]:
                continue

            # 时间窗口
            time_diff = abs((f1["time"] - f2["time"]).total_seconds()) / 60
            if time_diff > time_window_minutes:
                continue

            # 读取内容
            try:
                text1 = Path(f1["path"]).read_text(encoding="utf-8", errors="ignore")
                text2 = Path(f2["path"]).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # 关键词重叠
            kw1 = extract_keywords(text1)
            kw2 = extract_keywords(text2)
            common = kw1 & kw2

            if len(common) >= 3:
                results.append({
                    "file_a": f1["name"],
                    "file_b": f2["name"],
                    "type_a": f1["type"],
                    "type_b": f2["type"],
                    "time_gap_min": round(time_diff, 1),
                    "common_keywords": list(common)[:8],
                    "match_count": len(common),
                })

    results.sort(key=lambda x: x["match_count"], reverse=True)
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="跨格式模式匹配")
    parser.add_argument("--time-window", type=int, default=30, help="时间窗口(分钟)")
    args = parser.parse_args()

    print(f"🔗 跨格式模式匹配")
    print(f"  时间窗口: {args.time_window}分钟")
    print("=" * 40)

    files = collect_files()
    print(f"  文件: {len(files)} ({sum(1 for f in files if f['type']=='doc')} doc + "
          f"{sum(1 for f in files if f['type']=='script')} script)")

    results = detect_cross_format(files, time_window_minutes=args.time_window)
    print(f"  关联: {len(results)} 对")

    if results:
        print(f"\n  最强关联:")
        for r in results[:5]:
            print(f"    {r['file_a'][:30]:<32s} ↔ {r['file_b'][:30]:<32s}")
            print(f"      间隔{r['time_gap_min']}分 · {r['match_count']}个共享词: {', '.join(r['common_keywords'][:5])}")

    # 保存
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "time_window_minutes": args.time_window,
        "total_files": len(files),
        "total_pairs": len(results),
        "pairs": results[:20],
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 已保存: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
