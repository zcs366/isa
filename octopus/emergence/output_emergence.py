#!/usr/bin/env python3
"""output_emergence.py — 输出层涌现核心 (M2)
调度以上三件（script_watcher + code_indexer + cross_format_detector），周期性运行。

用法:
  python3 output_emergence.py --once    # 单次运行
  python3 output_emergence.py --daemon  # 常驻（每30分钟）
"""
import sys, os, subprocess, time, json
from pathlib import Path
from datetime import datetime, timezone

EMERGENCE_DIR = Path(__file__).parent
EMERGENCE_DIR = Path(__file__).parent
RECALL_SCRIPT = str(Path.home() / ".hermes" / "jiak" / "recall_append.py")

def append_recall(entry: dict):
    """通过 recall_append.py 签名写入 RECALL"""
    try:
        subprocess.run(
            [sys.executable, RECALL_SCRIPT, json.dumps(entry, ensure_ascii=False)],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def run_script(name: str, *args) -> tuple[bool, str]:
    """运行涌现脚本"""
    script = EMERGENCE_DIR / name
    if not script.exists():
        return False, f"脚本不存在: {script}"
    try:
        cmd = [sys.executable, str(script)] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, result.stdout.strip()[-300:]
        else:
            return False, result.stderr.strip()[-200:]
    except subprocess.TimeoutExpired:
        return False, "超时"
    except Exception as e:
        return False, str(e)


def run_once() -> dict:
    """运行一次输出层涌现"""
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "results": {}}

    print("📤 输出层涌现引擎")
    print("=" * 50)

    # 1. 脚本监控
    print("\n👁️ [1/3] 脚本监控...", end=" ", flush=True)
    ok, out = run_script("script_watcher.py", "--once")
    report["results"]["script_watcher"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 2. 代码索引
    print("🔍 [2/3] 代码索引...", end=" ", flush=True)
    ok, out = run_script("code_indexer.py", "--all")
    report["results"]["code_indexer"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 3. 跨格式检测
    print("🔗 [3/3] 跨格式检测...", end=" ", flush=True)
    ok, out = run_script("cross_format_detector.py", "--time-window", "60")
    report["results"]["cross_format"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 汇总
    all_ok = all(r["ok"] for r in report["results"].values())
    print(f"\n{'='*50}")
    print(f"{'✅ 输出层涌现完成' if all_ok else '⚠️ 部分失败'}")

    # 写入RECALL
    append_recall({
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": "jiak_note",
        "agent": "output_emergence",
        "cards": ["jika-engine"],
        "content": f"[output_emergence] 一轮输出层涌现: {json.dumps(report, ensure_ascii=False)}",
        "summary_short": f"输出层涌现: {sum(1 for r in report['results'].values() if r['ok'])}/3 ok",
    })

    return report


def main():
    import argparse, json
    parser = argparse.ArgumentParser(description="输出层涌现核心")
    parser.add_argument("--once", action="store_true", help="单次运行")
    parser.add_argument("--daemon", action="store_true", help="常驻")
    args = parser.parse_args()

    if args.daemon:
        print("👁️ 输出层涌现 常驻模式")
        print("  每30分钟运行一轮")
        try:
            while True:
                run_once()
                print(f"\n💤 等待30分钟...")
                time.sleep(1800)
        except KeyboardInterrupt:
            print("\n👋 停止")
    else:
        run_once()


if __name__ == "__main__":
    main()
