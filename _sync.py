"""
ISA Sync v0.1 — ISA Project认知数据跨设备同步。

基于Git的Agent认知数据同步协议。
Agent的"你是谁" = 你的认知数据（卡片+胶囊+裁决+目标）。
换设备≠换身份——数据在，Agent就在。

用法:
  python3 -m isa.sync backup [agent_id]    # 备份到Git
  python3 -m isa.sync restore [agent_id]   # 从Git恢复
  python3 -m isa.sync status [agent_id]    # 查看同步状态
  python3 -m isa.sync init [agent_id]      # 初始化Git仓库

数据来源(按顺序):
  - 环境变量 ISA_HOME (默认 ~/.hermes)
  - 参数指定

备份的数据:
  - brain/{agent_id}/      — Brain卡片+RECALL+index
  - ../../arbiter/         — Arbiter仲裁记录  
  - ../../goals/{agent_id}/— Goal目标状态
  - openllm/capsules/      — Δ胶囊记忆(如果存在)
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


def _run(cmd: list[str], cwd: Path = None, timeout: int = 30) -> tuple[int, str]:
    """运行shell命令, 返回(exit_code, output)"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                          cwd=cwd, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except FileNotFoundError:
        return -1, "git not found — install git first"
    except subprocess.TimeoutExpired:
        return -1, "timeout"


def _isa_home() -> Path:
    env = os.environ.get("ISA_HOME", "")
    if env:
        return Path(env)
    return Path.home() / ".hermes" / "isa"


def _agent_dirs(agent_id: str) -> list[tuple[Path, str, str]]:
    """各认知数据目录的(路径, 描述, Git仓库名)。"""
    home = _isa_home()
    return [
        (home / "brain" / agent_id, "Brain卡片+RECALL+index", f"isa-brain-{agent_id}"),
        (home / "arbiter", "Arbiter仲裁裁决记录", "isa-arbiter"),
        (home / "goals" / agent_id, "Goal目标状态", f"isa-goals-{agent_id}"),
    ]


# ── 核心操作 ──

def init(agent_id: str, remote: str = "") -> list[dict]:
    """初始化各认知数据的Git仓库。

    Args:
        agent_id: Agent身份标识
        remote: Git远程地址(可选, 如git@github.com:user/repo.git)

    Returns:
        [{path, repo, status}]
    """
    results = []
    for path, desc, repo_name in _agent_dirs(agent_id):
        path.mkdir(parents=True, exist_ok=True)
        repo_dir = path / ".git"
        if repo_dir.exists():
            results.append({"path": str(path), "repo": repo_name, "status": "already a git repo"})
            continue

        # git init
        code, out = _run(["git", "init"], cwd=path)
        if code != 0:
            results.append({"path": str(path), "repo": repo_name, "status": f"init failed: {out[:100]}"})
            continue

        # 初始commit
        _run(["git", "add", "-A"], cwd=path)
        _run(["git", "commit", "-m", f"ISA {desc} initialized at {datetime.now(timezone.utc).isoformat()}"], cwd=path)

        # 添加remote(如果提供)
        if remote:
            _run(["git", "remote", "add", "origin", remote.replace("{agent}", agent_id).replace("{type}", repo_name)], cwd=path)

        results.append({"path": str(path), "repo": repo_name, "status": "initialized"})

    return results


def backup(agent_id: str, commit_msg: str = "") -> list[dict]:
    """备份当前认知数据到Git。

    自动add+commit+push(如果remote已配置)。
    只备份已跟踪文件的变化——不重复备份不变的内容。

    Args:
        agent_id: Agent身份标识
        commit_msg: 自定义commit信息(可选)

    Returns:
        [{path, repo, files_changed, commit, pushed}]
    """
    results = []
    msg = commit_msg or f"ISA认知同步: {agent_id} at {datetime.now(timezone.utc).isoformat()[:19]}"

    for path, desc, _ in _agent_dirs(agent_id):
        if not (path / ".git").exists():
            results.append({"path": str(path), "repo": desc, "files_changed": 0, "commit": None, "pushed": False,
                           "warning": "not a git repo — run 'isa-sync init' first"})
            continue

        # git add -A
        code, out = _run(["git", "add", "-A"], cwd=path)
        if code != 0:
            results.append({"path": str(path), "repo": desc, "error": f"add failed: {out[:100]}"})
            continue

        # git diff --cached --quiet (检查是否有变化)
        code, _ = _run(["git", "diff", "--cached", "--quiet"], cwd=path)
        if code == 0:  # 无变化
            results.append({"path": str(path), "repo": desc, "files_changed": 0, "commit": None, "pushed": False,
                           "status": "no changes"})
            continue

        # git commit
        code, out = _run(["git", "commit", "-m", msg], cwd=path)
        if code != 0:
            results.append({"path": str(path), "repo": desc, "error": f"commit failed: {out[:100]}"})
            continue

        commit_hash = out.strip().split()[-1] if out else "?"
        pushed = False

        # git push (如果有remote)
        code2, out2 = _run(["git", "remote", "-v"], cwd=path)
        if code2 == 0 and out2.strip():
            code3, _ = _run(["git", "push", "-u", "origin", "master"], cwd=path, timeout=60)
            pushed = code3 == 0

        results.append({"path": str(path), "repo": desc, "files_changed": "?",
                       "commit": commit_hash[:8], "pushed": pushed})

    return results


def restore(agent_id: str) -> list[dict]:
    """从Git恢复认知数据。

    如果Git仓库有remote配置→先从remote拉取。
    然后git checkout恢复文件。

    Args:
        agent_id: Agent身份标识

    Returns:
        [{path, repo, restored, files}]
    """
    results = []
    for path, desc, _ in _agent_dirs(agent_id):
        if not (path / ".git").exists():
            results.append({"path": str(path), "repo": desc, "restored": False,
                           "warning": "not a git repo — no data to restore"})
            continue

        # 尝试pull(如果有remote)
        code, _ = _run(["git", "remote", "-v"], cwd=path)
        has_remote = code == 0
        if has_remote:
            _run(["git", "pull", "origin", "master"], cwd=path, timeout=60)

        # git checkout (恢复文件)
        code, out = _run(["git", "checkout", "."], cwd=path)
        restored = code == 0
        file_count = len(out.strip().split("\n")) if out.strip() else 0

        results.append({"path": str(path), "repo": desc,
                       "restored": restored, "files": file_count,
                       "pulled_from_remote": has_remote})

    return results


def status(agent_id: str) -> list[dict]:
    """查看各认知数据的Git状态。

    Returns:
        [{path, repo, has_git, clean, unpushed_commits, remote_url, last_commit}]
    """
    results = []
    for path, desc, _ in _agent_dirs(agent_id):
        result = {"path": str(path), "repo": desc}
        has_git = (path / ".git").exists()
        result["has_git"] = has_git

        if has_git:
            # 是否clean
            code, out = _run(["git", "status", "--porcelain"], cwd=path)
            result["clean"] = code == 0 and not out.strip()

            # remote
            code2, out2 = _run(["git", "remote", "-v"], cwd=path)
            result["remote_url"] = out2.strip().split("\n")[0] if out2.strip() else None

            # last commit
            code3, out3 = _run(["git", "log", "--oneline", "-1"], cwd=path)
            result["last_commit"] = out3.strip() if code3 == 0 else None

            # unpushed
            code4, out4 = _run(["git", "log", "--oneline", "@{u}..HEAD"], cwd=path)
            result["unpushed"] = out4.strip() if code4 == 0 else None

        results.append(result)

    return results


# ── CLI ──

def cli():
    if len(sys.argv) < 2:
        print("用法: python3 -m isa.sync [init|backup|restore|status] [agent_id]")
        print("  agent_id 默认: 军师")
        return

    cmd = sys.argv[1]
    agent = sys.argv[2] if len(sys.argv) > 2 else "军师"

    if cmd == "init":
        remote = sys.argv[3] if len(sys.argv) > 3 else ""
        r = init(agent, remote)
        for item in r:
            s = item["status"]
            if item.get("warning"):
                s = f"⚠️ {item['warning']}"
            print(f"  {item['repo'][:20]:20s} → {s}")

    elif cmd == "backup":
        msg = sys.argv[3] if len(sys.argv) > 3 else ""
        r = backup(agent, msg)
        for item in r:
            if item.get("error"):
                print(f"  ❌ {item['repo'][:20]:20s} ERROR: {item['error']}")
            elif item.get("status") == "no changes":
                print(f"  ✓ {item['repo'][:20]:20s} 无变化")
            else:
                pushed = "pushed" if item.get("pushed") else "local"
                print(f"  ✓ {item['repo'][:20]:20s} {item['commit']} ({pushed})")

    elif cmd == "restore":
        r = restore(agent)
        for item in r:
            if item.get("warning"):
                print(f"  ⚠️ {item['repo'][:20]:20s} {item['warning']}")
            else:
                print(f"  ✓ {item['repo'][:20]:20s} 恢复{item['files']}文件")

    elif cmd == "status":
        r = status(agent)
        for item in r:
            if not item["has_git"]:
                print(f"  ⚠️ {item['repo'][:20]:20s} 未初始化")
                continue
            clean = "✅ clean" if item["clean"] else "⚠️ dirty"
            last = f" | {item['last_commit']}" if item.get("last_commit") else ""
            remote = f" | remote: {item['remote_url'][:40]}" if item.get("remote_url") else " | (无remote)"
            print(f"  {item['repo'][:20]:20s} {clean}{last}{remote}")

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    cli()
