#!/usr/bin/env python3
"""章鱼喂食器 v3.0 — Tantivy 文档增量索引
用法: python3 octopus_feed.py [目录]
"""
import os, glob, sys
import tantivy
import jieba

OUTPUT = os.path.expanduser("~/hermes/output")
I_OUTPUT = "/mnt/i/hermes/output"
INDEX_DIR = os.path.expanduser("~/projects/isa/octopus/tantivy_index")


def build_docs_schema():
    builder = tantivy.SchemaBuilder()
    builder.add_text_field("id", stored=True)
    builder.add_text_field("title", stored=True)
    builder.add_text_field("tentacle", stored=True)
    builder.add_text_field("body", stored=True)
    return builder.build()


def feed_directory(dirpath):
    """批量索引目录中的 .md 文件到 Tantivy docs index"""
    docs_path = os.path.join(INDEX_DIR, "docs")
    if not os.path.exists(docs_path):
        print("❌ Tantivy docs index 不存在，先运行 octopus_index.py")
        return 0

    schema = build_docs_schema()
    index = tantivy.Index(schema, path=docs_path)
    writer = index.writer()
    count = 0

    for md in glob.glob(os.path.join(dirpath, "**", "*.md"), recursive=True):
        try:
            with open(md) as f:
                content = f.read()
        except Exception:
            continue

        # 提取标题
        title = ""
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # 提取分类
        rel = os.path.relpath(md, OUTPUT)
        parts = rel.split(os.sep)
        category = parts[0] if len(parts) > 1 else "root"

        # 结巴分词
        segmented = " ".join(jieba.cut(content))

        writer.add_document(tantivy.Document(
            id=md,
            title=title,
            tentacle=category,
            body=segmented,
        ))
        count += 1

    writer.commit()
    return count


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    total = 0
    if target:
        total = feed_directory(target)
        print(f"🐙 章鱼喂食 v3.0 (Tantivy): {total} 篇文档索引完成")
        print(f"📁 来源: {target}")
    else:
        # 默认双源：C盘工作区 + I盘主仓
        n1 = feed_directory(OUTPUT)
        n2 = feed_directory(I_OUTPUT)
        total = n1 + n2
        print(f"🐙 章鱼喂食 v3.0 (Tantivy): {total} 篇文档索引完成")
        print(f"📁 C盘工作区: {n1} 篇 | I盘主仓: {n2} 篇")


if __name__ == "__main__":
    main()
