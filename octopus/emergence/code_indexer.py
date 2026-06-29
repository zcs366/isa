#!/usr/bin/env python3
"""code_indexer.py — 代码全文索引 (M2)
扩展 octopus_feed.py，新增 .py/.sh/.yaml/.json/.toml 索引通道。
将代码文件分词后索引到章鱼的 Tantivy docs 索引。

用法:
  python3 code_indexer.py <目录>   # 索引指定目录
  python3 code_indexer.py --all    # 索引所有预置目录
"""
import os, sys, glob
from pathlib import Path

OCTOPUS_DIR = Path.home() / "projects" / "isa" / "octopus"
TANTIVY_DIR = OCTOPUS_DIR / "tantivy_index" / "docs"

# 可索引的代码扩展名
CODE_EXTENSIONS = {".py", ".sh", ".bash", ".yaml", ".yml", ".json", ".toml", ".md", ".txt", ".cfg", ".conf"}

# 默认扫描目录
DEFAULT_DIRS = [
    Path.home() / "projects" / "isa" / "octopus" / "emergence",
    Path.home() / "hermes" / "output" / "scripts",
    Path.home() / ".hermes" / "jiak",
]


def build_schema():
    """构建 Tantivy schema（与章鱼docs索引一致）"""
    import tantivy
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("title", stored=True)
    builder.add_text_field("tentacle", stored=True)
    builder.add_text_field("body", stored=True)
    return builder.build()


def index_directory(dirpath: Path, index) -> int:
    """索引一个目录中的代码文件"""
    import tantivy
    import jieba

    count = 0
    writer = index.writer()

    for ext in CODE_EXTENSIONS:
        for f in sorted(dirpath.rglob(f"*{ext}")):
            # 跳过隐藏文件和缓存
            if any(p.startswith(".") for p in f.parts):
                continue
            if "__pycache__" in f.parts:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if not content.strip():
                continue

            # 分词
            segmented = " ".join(jieba.cut(content))

            try:
                writer.add_document(tantivy.Document(
                    id=str(f),
                    title=f.name,
                    tentacle="code",
                    body=segmented,
                ))
                count += 1
            except Exception:
                continue

    writer.commit()
    return count


def main():
    import argparse, tantivy
    parser = argparse.ArgumentParser(description="代码全文索引")
    parser.add_argument("dirs", nargs="*", help="要索引的目录")
    parser.add_argument("--all", action="store_true", help="索引所有预置目录")
    args = parser.parse_args()

    if not os.path.exists(TANTIVY_DIR):
        print(f"❌ Tantivy 文档索引不存在: {TANTIVY_DIR}")
        print("   先运行 octopus_index.py")
        return

    dirs = []
    if args.all:
        dirs = DEFAULT_DIRS
    elif args.dirs:
        dirs = [Path(d) for d in args.dirs]
    else:
        dirs = DEFAULT_DIRS

    print(f"🔍 代码全文索引")
    print(f"  索引库: {TANTIVY_DIR}")
    print("=" * 40)

    schema = build_schema()
    index = tantivy.Index(schema, path=str(TANTIVY_DIR))
    total = 0

    for d in dirs:
        if not d.exists():
            print(f"  ⚠️ 目录不存在: {d}")
            continue
        count = index_directory(d, index)
        total += count
        print(f"  📁 {d}: {count} 文件")

    print(f"\n  ✅ 总计: {total} 个代码文件索引完成")


if __name__ == "__main__":
    main()
