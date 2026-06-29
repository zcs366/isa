#!/usr/bin/env python3
"""ffata_sa.py — AGI贯通师 SA (M1)
继承SALifecycle，周期性运行所有涌现引擎。

用法:
  python3 ffata_sa.py --once     # 单次运行（不启动SA生命周期）
  python3 ffata_sa.py --daemon   # 常驻运行
"""
import json, os, sys, time, subprocess
from pathlib import Path
from datetime import datetime, timezone

EMERGENCE_DIR = Path(__file__).parent
RECALL_PATH = Path.home() / ".hermes" / "jiak" / "RECALL.jsonl"
SEMANTIC_FIELD = Path.home() / ".hermes" / "semantic_field"

# 尝试导入SALifecycle，失败则降级
try:
    sys.path.insert(0, str(Path.home() / "projects" / "openllm-memory" / "src"))
    from openllm_memory.capsule.resonance import SharedMemory, SALifecycle
    _HAVE_SA = True
except ImportError:
    _HAVE_SA = False
    SharedMemory = None
    SALifecycle = None


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
    """运行一个涌现脚本"""
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


def run_all_engines() -> dict:
    """运行所有涌现引擎，返回结果报告"""
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "results": {}}

    print("🔮 AGI贯通师 — 涌现引擎全开")
    print("=" * 50)

    # 1. jiak知识图谱
    print("\n📊 [1/5] jiak知识图谱...", end=" ", flush=True)
    ok, out = run_script("jiak_graph.py", "--save")
    report["results"]["jiak_graph"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 2. jiak涌现
    print("🔍 [2/5] jiak涌现(关键词模式)...", end=" ", flush=True)
    ok, out = run_script("jiak_emergence.py", "--no-llm")
    report["results"]["jiak_emergence"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 3. 递归回流
    print("🔄 [3/5] 递归回流...", end=" ", flush=True)
    ok, out = run_script("recursive_loop.py")
    report["results"]["recursive_loop"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 4. 共鸣共振
    print("🎯 [4/5] 共鸣共振...", end=" ", flush=True)
    ok, out = run_script("symres.py", "--recent", "200")
    report["results"]["symres"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 5. 涌现引擎
    print("🧠 [5/5] 涌现引擎...", end=" ", flush=True)
    ok, out = run_script("emergence.py", "--once")
    report["results"]["emergence"] = {"ok": ok, "output": out[:100]}
    print("✅" if ok else f"❌ {out[:50]}")

    # 汇总
    all_ok = all(r["ok"] for r in report["results"].values())
    print(f"\n{'='*50}")
    print(f"{'✅ 全部完成' if all_ok else '⚠️ 部分失败'}")

    return report


def run_with_sa(channel: str = "ffata"):
    """以SA生命周期运行"""
    if not _HAVE_SA:
        print("❌ SALifecycle 不可用，降级为 --once 模式")
        run_all_engines()
        return

    sm = SharedMemory(str(SEMANTIC_FIELD))
    sa = SALifecycle(
        soul_id="soul.hermes.ffata",
        channel=channel,
        shared_memory=sm,
        name="ffata-sa",
    )
    print(f"🔮 AGI贯通师 SA 上线 (channel={channel})")

    try:
        report = run_all_engines()

        # 写入RECALL
        append_recall({
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "jiak_note",
            "agent": "ffata_sa",
            "cards": ["jika-engine"],
            "content": f"[ffata] 一轮涌现完成: {json.dumps(report, ensure_ascii=False)}",
            "summary_short": f"ffata一轮: {sum(1 for r in report['results'].values() if r['ok'])}/5 ok",
        })
    finally:
        sa.goodbye()
        print("👋 AGI贯通师 SA 下线")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AGI贯通师 SA")
    parser.add_argument("--once", action="store_true", help="单次运行（不含SA生命周期）")
    parser.add_argument("--daemon", action="store_true", help="常驻运行")
    parser.add_argument("--channel", default="ffata", help="SA channel")
    args = parser.parse_args()

    if args.once:
        run_all_engines()
    elif args.daemon:
        print("👁️ AGI贯通师 常驻模式")
        print("  每30分钟运行一轮涌现引擎")
        try:
            while True:
                run_with_sa(args.channel)
                print(f"\n💤 等待30分钟...")
                time.sleep(1800)
        except KeyboardInterrupt:
            print("\n👋 停止")
    else:
        run_with_sa(args.channel)


if __name__ == "__main__":
    main()
