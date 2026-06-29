#!/usr/bin/env python3
"""script_watcher.py — /tmp 脚本监控 (M2)
用 inotify 监控 /tmp/*.py /tmp/*.sh，新文件自动归档到 output/scripts/ 并触发索引。

用法:
  python3 script_watcher.py --once   # 一次性扫描
  python3 script_watcher.py --watch  # 持续监控（需要 inotify）
"""
import os, sys, shutil, subprocess, glob
from pathlib import Path

OUTPUT_SCRIPTS = Path.home() / "hermes" / "output" / "scripts"
OCTOPUS_DIR = Path.home() / "projects" / "isa" / "octopus"


def ensure_output_dir():
    OUTPUT_SCRIPTS.mkdir(parents=True, exist_ok=True)


def discover_temp_scripts() -> list[Path]:
    """发现 /tmp 中的脚本文件"""
    scripts = []
    for pattern in ["/tmp/*.py", "/tmp/*.sh", "/tmp/*.bash"]:
        for f in glob.glob(pattern):
            p = Path(f)
            # 跳过临时缓存文件
            if p.name.startswith("tmp") or p.name.startswith("."):
                continue
            # 跳过已知的脚本
            if p.name in ("jieba.cache",):
                continue
            scripts.append(p)
    return scripts


def archive_script(src: Path) -> Path | None:
    """归档脚本到 output/scripts/"""
    dst = OUTPUT_SCRIPTS / src.name
    # 如果已存在，加时间戳
    if dst.exists():
        stamp = src.stat().st_mtime_ns
        dst = OUTPUT_SCRIPTS / f"{src.stem}_{stamp}{src.suffix}"

    try:
        shutil.copy2(str(src), str(dst))
        return dst
    except Exception:
        return None


def index_scripts():
    """触发章鱼索引"""
    try:
        result = subprocess.run(
            [sys.executable, str(OCTOPUS_DIR / "octopus_feed.py"), str(OUTPUT_SCRIPTS)],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout.strip()[-200:]
    except Exception as e:
        return str(e)


def run_once() -> int:
    """一次性扫描归档"""
    ensure_output_dir()
    scripts = discover_temp_scripts()
    archived = 0

    for src in scripts:
        dst = archive_script(src)
        if dst:
            print(f"  📦 {src.name} → {dst}")
            archived += 1

    if archived > 0:
        out = index_scripts()
        print(f"  🐙 章鱼索引: {out}")
    else:
        print("  ✅ 无新脚本")

    return archived


def main():
    import argparse
    parser = argparse.ArgumentParser(description="/tmp脚本监控")
    parser.add_argument("--once", action="store_true", help="一次性扫描")
    args = parser.parse_args()

    print("👁️ 脚本监控")
    print("=" * 40)
    run_once()


if __name__ == "__main__":
    main()
