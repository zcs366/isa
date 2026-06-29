#!/bin/bash
# BGE-large-zh 手动下载脚本
# 用法: bash download_bge_large.sh
# 下载到: /mnt/d/models/bge-large-zh-v1.5/

set -e

MODEL_DIR="/mnt/d/models/bge-large-zh-v1.5"
mkdir -p "$MODEL_DIR"

echo "=== 下载 BGE-large-zh (1.3GB/12文件) ==="
echo "目标: $MODEL_DIR"
echo ""

# 方案一: HF镜像 (推荐)
echo "--- 方案1: hf-mirror ---"
pip install huggingface_hub -q 2>/dev/null
HF_ENDPOINT=https://hf-mirror.com python3 -c "
import os
os.environ['HF_HOME'] = '/mnt/d/.cache/huggingface'
from huggingface_hub import snapshot_download
snapshot_download('BAAI/bge-large-zh-v1.5', local_dir='$MODEL_DIR', resume_download=True, max_workers=2)
print('方案1成功!')
" 2>&1 && echo "✅ 下载完成" && exit 0

echo "方案1失败,尝试方案2..."

# 方案二: ModelScope
echo "--- 方案2: ModelScope ---"
pip install modelscope -q 2>/dev/null
python3 -c "
from modelscope.hub.snapshot_download import snapshot_download
snapshot_download('BAAI/bge-large-zh-v1.5', cache_dir='/mnt/d/models/hub')
print('方案2成功!')
" 2>&1 && echo "✅ 下载完成" && exit 0

echo "方案2失败,尝试方案3..."

# 方案三: 直连HF
echo "--- 方案3: 直连HF ---"
python3 -c "
import os
os.environ['HF_HOME'] = '/mnt/d/.cache/huggingface'
from huggingface_hub import snapshot_download
snapshot_download('BAAI/bge-large-zh-v1.5', local_dir='$MODEL_DIR', resume_download=True, max_workers=2)
print('方案3成功!')
" 2>&1 && echo "✅ 下载完成" && exit 0

echo ""
echo "❌ 三种方案全部失败。请检查网络连接后重试。"
echo "手动地址: https://huggingface.co/BAAI/bge-large-zh-v1.5"
exit 1
