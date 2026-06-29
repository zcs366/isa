#!/usr/bin/env python3
"""章鱼文件扫描器 v1.0 — 本地全域文件扫描+文本提取
用法:
  python3 octopus_files_scanner.py                           # 全量扫描
  python3 octopus_files_scanner.py --incremental             # 增量扫描（检查mtime）
  python3 octopus_files_scanner.py --test-pdf                # 测试PDF提取
  python3 octopus_files_scanner.py --test-ocr                # 测试图片OCR

扫描C:/D:/I:用户目录下所有文件，提取文本内容，输出JSONL到标准输出。
供 octopus_index.py 消费建Tantivy索引。
"""
import os, sys, json, hashlib, time, re
from datetime import datetime

# ─── 配置 ─────────────────────────────────────────────────

# 扫描目录（只扫用户数据，不扫系统）
_BASE_SCAN_DIRS = [
    "/mnt/c/Users/Administrator/Desktop",
    "/mnt/c/Users/Administrator/Documents",
    "/mnt/c/Users/Administrator/Downloads",
    os.path.expanduser("~"),           # /home/zcs
    "/mnt/i/hermes",                   # 主工作区
]

# 排除目录（正则）
EXCLUDE_DIRS = re.compile(
    r"(node_modules|\.git|__pycache__|venv|\.venv|\.cache|"
    r"AppData|Windows|Program Files|ProgramData|"
    r"temp|tmp|\.tmp|\.npm|\.yarn|\.pnpm|\.next|"
    r"\.mypy_cache|\.pytest_cache|\.ruff_cache|"
    r"\.terraform|\.serverless)" ,
    re.IGNORECASE
)

# 文本格式（直接读，零依赖）
TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".csv", ".xml",
    ".html", ".htm", ".css", ".scss", ".less",
    ".sh", ".bash", ".zsh", ".env", ".cfg", ".ini",
    ".conf", ".log", ".sql", ".rst", ".tex",
    ".c", ".cpp", ".h", ".hpp", ".java", ".rs", ".go",
    ".rb", ".php", ".pl", ".lua", ".swift", ".kt",
    ".vue", ".svelte", ".astro",
    ".dockerfile", ".makefile", ".cmake",
}

# 二进制格式（需要额外依赖）
BINARY_FORMATS = {
    ".pdf":  {"extract": "fitz", "label": "PDF"},
    ".docx": {"extract": "docx", "label": "Word"},
    ".jpg":  {"extract": "ocr",  "label": "图片"},
    ".jpeg": {"extract": "ocr",  "label": "图片"},
    ".png":  {"extract": "ocr",  "label": "图片"},
}

STATE_FILE = os.path.expanduser("~/projects/isa/octopus/.file_state.json")


# ─── 文本提取 ─────────────────────────────────────────────

def extract_text_from_file(filepath):
    """从文件提取文本内容。返回 (text, format_type) 或无内容时返回 ("", "unknown")"""
    ext = os.path.splitext(filepath)[1].lower()
    
    # 文本格式
    if ext in TEXT_EXTENSIONS:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(4096)  # 限4096字符
            return content.strip(), "text"
        except Exception:
            return "", "text_fail"
    
    # PDF
    if ext == ".pdf":
        return extract_pdf(filepath)
    
    # DOCX
    if ext == ".docx":
        return extract_docx(filepath)
    
    # 图片OCR
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"):
        return extract_ocr(filepath)
    
    return "", "unknown"


def extract_pdf(filepath):
    """用 PyMuPDF 提取PDF文字"""
    try:
        import fitz
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > 4000:
                text = text[:4000]
                break
        doc.close()
        return text.strip()[:4096], "pdf"
    except Exception as e:
        # fallback: pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                text = "".join(p.extract_text() or "" for p in pdf.pages[:3])
            return text.strip()[:4096], "pdf"
        except Exception:
            return f"[PDF提取失败: {e}]", "pdf_fail"


def extract_docx(filepath):
    """用 python-docx 提取Word文字"""
    try:
        from docx import Document
        doc = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs)
        return text.strip()[:4096], "docx"
    except Exception as e:
        return f"[DOCX提取失败: {e}]", "docx_fail"


def extract_ocr(filepath):
    """用 pytesseract 对图片做OCR"""
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(filepath)
        # 限大图
        if img.size[0] * img.size[1] > 4000 * 4000:
            img.thumbnail((2000, 2000))
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        return text.strip()[:1024], "ocr"  # OCR取前1024字
    except Exception as e:
        return f"[OCR失败: {e}]", "ocr_fail"


# ─── 文件扫描 ─────────────────────────────────────────────

def scan_files(incremental=False, scan_d=False):
    """扫描文件系统，返回 (files_info, stats)"""
    files_info = []
    stats = {"dirs": 0, "files": 0, "text": 0, "pdf": 0, "docx": 0, "ocr": 0,
             "binary": 0, "skipped": 0, "errors": 0}
    
    scan_dirs = list(_BASE_SCAN_DIRS)
    if scan_d:
        scan_dirs.append("/mnt/d")
    file_state = {}
    if incremental and os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            file_state = json.load(f)
    
    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            continue
        for root, dirs, files in os.walk(scan_dir, topdown=True):
            # 排除目录
            dirs[:] = [d for d in dirs if not EXCLUDE_DIRS.search(os.path.join(root, d))]
            stats["dirs"] += 1
            
            for fname in files:
                filepath = os.path.join(root, fname)
                stats["files"] += 1
                
                # 跳过超大文件（>50MB）
                try:
                    fsize = os.path.getsize(filepath)
                    if fsize > 50 * 1024 * 1024:
                        stats["binary"] += 1
                        continue
                except OSError:
                    stats["skipped"] += 1
                    continue
                
                ext = os.path.splitext(fname)[1].lower()
                
                # 增量：检查mtime
                try:
                    mtime = os.path.getmtime(filepath)
                except OSError:
                    stats["skipped"] += 1
                    continue
                
                if incremental and filepath in file_state:
                    if file_state[filepath]["mtime"] == mtime:
                        continue  # 没变，跳过
                
                # 提取文本
                text, fmt = extract_text_from_file(filepath)
                
                if fmt == "text":
                    stats["text"] += 1
                elif fmt == "pdf":
                    stats["pdf"] += 1
                elif fmt == "docx":
                    stats["docx"] += 1
                elif fmt == "ocr":
                    stats["ocr"] += 1
                elif fmt in ("text_fail", "pdf_fail", "docx_fail", "ocr_fail", "unknown"):
                    stats["errors"] += 1
                
                files_info.append({
                    "path": filepath,
                    "name": fname,
                    "ext": ext,
                    "size": fsize,
                    "mtime": mtime,
                    "content": text[:4096],
                    "fmt": fmt,
                })
                
                # 增量：保存状态
                if incremental:
                    file_state[filepath] = {"mtime": mtime}
    
    # 保存增量状态
    if incremental:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(file_state, f)
    
    return files_info, stats


def main():
    if "--test-pdf" in sys.argv:
        import glob
        pdfs = glob.glob("/mnt/c/Users/Administrator/Desktop/*.pdf")
        pdfs += glob.glob(os.path.expanduser("~/*.pdf"))
        if not pdfs:
            pdfs = glob.glob("/mnt/i/hermes/papers/**/*.pdf", recursive=True)[:3]
        for pdf in pdfs[:3]:
            text, fmt = extract_pdf(pdf)
            print(f"\n📄 {os.path.basename(pdf)}")
            print(f"   格式: {fmt}")
            print(f"   长度: {len(text)}")
            print(f"   内容前200: {text[:200]}")
        return

    if "--test-ocr" in sys.argv:
        import glob
        imgs = glob.glob("/mnt/c/Users/Administrator/Desktop/*.png") + \
               glob.glob("/mnt/c/Users/Administrator/Desktop/*.jpg")
        for img in imgs[:3]:
            text, fmt = extract_ocr(img)
            print(f"\n🖼️  {os.path.basename(img)}")
            print(f"   格式: {fmt}")
            print(f"   内容: {text[:200]}")
        return

    incremental = "--incremental" in sys.argv
    scan_d = "--scan-d" in sys.argv
    label = "增量" if incremental else "全量"
    print(f"🐙 章鱼文件扫描 v1.0 ({label})", file=sys.stderr)
    if scan_d:
        print(f"   + D盘", file=sys.stderr)
    print(f"   扫描目录: {len(_BASE_SCAN_DIRS) + (1 if scan_d else 0)} 个", file=sys.stderr)

    t0 = time.time()
    files_info, stats = scan_files(incremental, scan_d)
    elapsed = time.time() - t0

    # 输出JSONL到stdout（供octopus_index.py消费）
    for f in files_info:
        print(json.dumps(f, ensure_ascii=False))

    # 统计到stderr
    print(f"\n📊 统计 ({elapsed:.1f}s)", file=sys.stderr)
    print(f"   目录: {stats['dirs']}", file=sys.stderr)
    print(f"   文件: {stats['files']}", file=sys.stderr)
    print(f"   ├─ 文本: {stats['text']}", file=sys.stderr)
    print(f"   ├─ PDF: {stats['pdf']}", file=sys.stderr)
    print(f"   ├─ DOCX: {stats['docx']}", file=sys.stderr)
    print(f"   ├─ OCR: {stats['ocr']}", file=sys.stderr)
    print(f"   ├─ 超大(>50MB): {stats['binary']}", file=sys.stderr)
    print(f"   └─ 错误: {stats['errors']}", file=sys.stderr)
    print(f"   索引: {len(files_info)} 条", file=sys.stderr)

    # 增量模式：写状态文件
    if incremental:
        print(f"   状态文件: {STATE_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
