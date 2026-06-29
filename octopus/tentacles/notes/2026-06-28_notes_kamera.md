# Kamera: Unified Position-Invariant Multimodal KV Cache for Training-Free Reuse

**来源：** arXiv 2606.23581  
**日期：** 2026-06-28  
**标签：** #KV-Cache #多模态 #推理加速 #RoPE #位置不变性

---

## 问题陈述

多模态Agent在视频帧、UI截图、渲染产物之间反复来回查看，每次上下文窗口滑动都重新编码。现有的prefix cache只能在固定前置位置复用，无法处理非开头位置的KV重用。

核心发现：朴素KV重用唯一丢失的是**跨组块条件依赖**（cross-chunk conditioning）——即一个组块从其邻居处吸收的绑定信息。单跳读出可通过标准state-merge（FlashAttention）精确恢复，但多跳精度减半。

> "盲重用完好保留单跳召回，但多跳精度减半；这是此前位置无关型缓存未能解决的失效模式。"

---

## 方法：位置无关KV缓存

### 核心方程

```
KV̂(B|A) = R(δ)·KV(B|∅) + UₘVₘᵀ
```

- **Relocate（精确）：** R(δ) 将存储的K的RoPE相位重新旋转到新位置
- **Patch（条件矫正）：** UₘVₘᵀ = rank-m SVD of Δ = KV(B|A) - KV(B|∅)

### 统一覆盖三种注意力架构

- **MLA（DeepSeek）：** latent cKV不含RoPE；只需重新旋转64维decoupled kpe
- **GQA（Qwen）：** 对整个K重新应用RoPE旋转；对每个KV-head的K和V都做patch
- **MHA：** 视为GQA的特例（每个query-head对应1个KV-head），处理方式相同

---

## Δ丢失项的结构性质

1. **特征维度低秩：** 功能秩 m≈32 即可恢复输出分布（KL plateau），远低于~120个携带90%原始能量的SVD成分
2. **令牌维度弥散：** 不存在小的"绑定令牌集"；最优令牌选择器也需要约50%的令牌
3. **深层主导：** Δ的相对范数随深度增长（浅层0.08→深层0.49）；单层注入在浅层只解释27%，但深层解释~97%

> "薄补丁足以携带损失（低秩），令牌子集则不能（弥散），且修正必须存在于深层。"

---

## 三种窗口操作

### 1. Reorder（重排序）
不同顺序的同组块共享一个orbit-patch。K=3（3!种顺序）和K=4（4!种顺序）穷举测试：η_orbit=0.92≈η_exact=0.94，架构无关。

### 2. Sliding-Window Survival（窗口滑动）
最旧组块离开时，幸存块只需重新旋转RoPE（R(δ)）。GQA KL=0.015，MLA KL=0.023，近乎无损。

### 3. Recall（可逆式驱逐）
当缓存被完全替换后，仍可通过rank-32 patch恢复。GQA η=0.87，deepstack η=0.96，MLA η=0.81。

| 事件 | 架构 | 盲重用 | 新鲜Patch | 翻转恢复 |
|------|------|--------|-----------|---------|
| Recall | GQA | η=-0.68 | 0.87(r32) | 0.25→0.75 |
| Recall | deepstack | η=-2.85 | 0.96(r32) | 0.00→1.00 |
| Recall | MLA | η=+0.29 | 0.81(r32) | 0.00→0.67 |

---

## 精度与部署效果

### 准确率恢复
- **MM-NIAH：** 盲重用精度减半（检索0.74→0.38，推理0.59→0.41）；rank-16 patch恢复上限（0.72/0.64）
- **两页文档QA：** MLA盲重用0.28→0.15；rank-64 patch恢复至0.28
- **MileBench时序：** rank-64 patch恢复97%的答案翻转；VLCache/CacheBlend仍接近盲用基线

### 引擎实现（SGLang）
- KV重建误差在bf16舍入噪声水平内（残余next-token KL ≈10⁻³）
- 比盲重用低两个数量级（0.03-0.12）
- Video-MME和EgoSchema上下流准确率与re-prefill上限相差仅1-3个百分点

### 成本分析
- **显存：** rank-64 patch ≈ 段KV字节的25%；rank-16 ≈ 6%
- **摊还：** 约9次复用即超过每次prefill基线
- **TTFT加速：** 长视频可达29倍（仅prefill阶段）

---

## 架构通用性

六种骨干网络验证效果一致（gap@64=0.85-0.96）：Qwen2.5-VL、Qwen3-VL、InternVL3-8B、DeepSeek-VL、InternVL-V1.1、Phi-3.5-V。仅在弱模型（SmolVLM2、LLaVA-1.5）上无此效应——说明该不足是"能力强模型"的专属特征。

## 模态差异

- **视觉/视频：** 效果最显著
- **音频：** 较小且部分可恢复（Qwen2.5-Omni, n=40）
- **稠密文本（MuSiQue 2-hop）：** 无差距——该效应是**冗余令牌流**的特性
- **文档图像：** 丢失绑定；但同为事实的文本令牌则不丢失

---

## 意义

Kamera是首个统一的、训练无关的位置不变多模态KV缓存方案。核心洞察——跨组块条件依赖是低秩结构——使得一个极轻量的rank-16/rank-32补丁就能近乎完美恢复精度。"Relocate the key, patch the lost conditioning"的双操作框架优雅统一了三种主流注意力架构和五种滑动窗口场景。TTFT提升高达45倍（原文claims）、29倍（视频prefill），显存开销仅为完整segment的6-25%，工程实用性极高。推理即用的性质使其可无缝整合到现有SGLang/vLLM流水线中。

**局限性：** patch在稠密文本中无效（不存在冗余令牌流），纯文本场景无收益；缓存复用约需9次才能摊销patch的额外开销。
