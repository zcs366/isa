#!/usr/bin/env python3
"""八触须格式校验器 v1.0 — 强制性格式合规检查

用法:
  python3 validate_tentacle.py <file.md>          # 单文件校验
  python3 validate_tentacle.py <dir/>              # 目录递归校验
  python3 validate_tentacle.py <file.md> --fix     # 修复(补关键词行等)

返回值: 0=合规, 1=不合规

由IKO执行，所有SA产出写入tentacles/前必须通过此校验。
"""
import os, re, sys

TENTACLE_TYPES = {
    "memo":     {"trigger": "阶段性成果总结、架构说明、系统设计",     "keyword": "状态"},
    "pal":      {"trigger": "计划清单、任务分解、优先级",             "keyword": "计划"},
    "analysis": {"trigger": "深度分析、对比研究、评估可行性",         "keyword": "分析"},
    "intel":    {"trigger": "情报搜集、竞品动态、行业趋势",           "keyword": "情报"},
    "execution":{"trigger": "任务完成、代码变更、测试结果",           "keyword": "执行"},
    "meeting":  {"trigger": "合议、讨论要点、待办、分歧",             "keyword": "会议"},
    "techdoc":  {"trigger": "联邦法、协议标准、API说明、配置指南",    "keyword": "技术"},
    "lesson":   {"trigger": "踩坑记录、最佳实践、复盘",               "keyword": "决策"},
}

ISSUE_TEMPLATE = {
    "memo":     "memo",
    "pal":      "pal",
    "analysis": "analysis",
    "intel":    "intel",
    "execution":"execution",
    "meeting":  "meeting",
    "techdoc":  "techdoc",
    "lesson":   "lesson",
    "template": "template",
    "reference":"reference",
}

def detect_tentacle_type(content, path):
    """从内容或路径推断触须类型"""
    # 优先从路径推断
    for t in TENTACLE_TYPES:
        if f"/{t}/" in path or path.startswith(t):
            return t
    # 再从关键词推断
    for t, meta in TENTACLE_TYPES.items():
        if meta["keyword"] in content[:500]:
            return t
    return "unknown"

def validate_file(filepath, fix=False):
    """校验单个文件，返回 (pass, [errors], [warnings])"""
    errors = []
    warnings = []
    
    try:
        with open(filepath) as f:
            content = f.read()
    except Exception as e:
        return False, [f"读取失败: {e}"], []

    if not content.strip():
        return False, ["文件为空"], []

    # === 必检项 ===
    
    # 1. 标题（# 开头，含核心术语）
    title_line = ""
    for line in content.split("\n"):
        if line.startswith("# "):
            title_line = line[2:].strip()
            break
    if not title_line:
        errors.append("❌ 缺标题行 (# 开头)")
    elif len(title_line) < 5:
        warnings.append("⚠️ 标题过短 (<5字)，FTS5命中率低")

    # 2. 关键词行（> 作者/签发人 · 关键词：）
    kw_line = ""
    for line in content.split("\n"):
        if "关键词" in line and "：" in line:
            kw_line = line.strip()
            break
    if not kw_line:
        errors.append("❌ 缺关键词行（> * · 关键词：词1, 词2）")

    # 3. ## 结构化章节
    h2_count = len(re.findall(r'^## ', content, re.M))
    if h2_count == 0:
        errors.append("❌ 缺 ## 章节标题（至少1个二级标题）")
    elif h2_count == 1:
        warnings.append("⚠️ 仅1个二级标题，章节结构建议丰富")

    # 4. 文件名格式：YYYY-MM-DD_{触须}_{标题}.md
    basename = os.path.basename(filepath)
    if not re.match(r'^\d{4}-\d{2}-\d{2}_[a-z]+_', basename):
        warnings.append(f"⚠️ 文件名格式非标准: {basename}（建议 YYYY-MM-DD_{'{触须}'}_{'{标题}'}.md）")

    # 5. 触须类型判断
    tentacle = detect_tentacle_type(content, filepath)
    relevant = TENTACLE_TYPES.get(tentacle)
    if relevant:
        # 匹配 "## 结论" / "## 五、结论" / "## 结论与待办" 等变体
        has_conclusion = bool(re.search(r'^## .*(?:结论|总结|小结)', content, re.M))
        has_todo = bool(re.search(r'^## .*(?:待办|TODO|行动|下一步)', content, re.M))
        if not has_conclusion:
            errors.append(f"❌ {tentacle}类文档缺结论章节（## X、结论/## 结论与总结）")
        if not has_todo:
            warnings.append(f"⚠️ {tentacle}类文档建议含待办/行动章节")

    if fix and errors:
        # 修复：补关键词行（最小修复）
        fixed = content
        if "关键词" not in fixed[:200]:
            # 在第一个空行后插入关键词行
            lines = fixed.split("\n")
            insert_at = 0
            for i, line in enumerate(lines):
                if line.strip() == "" and i > 0:
                    insert_at = i + 1
                    break
            if insert_at == 0:
                insert_at = 1
            kw_guess = ", ".join(w for w in tentacle.split())
            lines.insert(insert_at, f"> 签发人：军师 · 关键词：{kw_guess}")
            fixed = "\n".join(lines)
        with open(filepath, "w") as f:
            f.write(fixed)
        return False, errors, warnings  # 修复后仍需人工确认

    return len(errors) == 0, errors, warnings


def main():
    if len(sys.argv) < 2:
        print("用法: python3 validate_tentacle.py <file.md|dir/> [--fix]")
        sys.exit(1)

    path = sys.argv[1]
    fix = "--fix" in sys.argv

    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        files = []
        for root, dirs, fnames in os.walk(path):
            for f in fnames:
                if f.endswith(".md"):
                    files.append(os.path.join(root, f))
    else:
        print(f"❌ 路径不存在: {path}")
        sys.exit(1)

    total = len(files)
    passed = 0
    failed = 0

    for f in sorted(files):
        ok, errors, warnings = validate_file(f, fix=fix)
        status = "✅" if ok else "❌"
        rel = os.path.relpath(f)
        if ok:
            passed += 1
        else:
            failed += 1
        
        if errors or warnings:
            print(f"\n  {status} {rel}")
            for e in errors:
                print(f"    {e}")
            for w in warnings:
                print(f"    {w}")
        else:
            pass  # 完全合规，静默

    print(f"\n{'='*40}")
    print(f"📊 总计: {total} 文件 | ✅ 通过: {passed} | ❌ 不通过: {failed}")
    
    if failed > 0:
        print(f"\n🏴 IKO注意: {failed} 文件不合规，需整改后重新提交")
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
