# 精读笔记：Harness Sensitivity Is Non-Monotone Across LLM Agent Tiers

**来源：** arXiv:2605.26731 | **作者：** Yong-eun Cho, KailosLab | **日期：** 2026-05

---

## 核心贡献：否定单调假设

大规模实验（**432次运行**：6模型 × 3 harness × 24任务）系统性地否定了"能力越强，结构化引导需求越少"的**单调逆假说**。关键发现：Harness敏感性**非单调**，取决于模型类型（chat vs. reasoning）和指令微调质量，而非单纯的参数规模。

## 实验设计

**HEAT-24基准：** 6类24个确定性合成任务——`inspect_local`（本地检查）、`structured_edit`（结构化编辑）、`format_sensitive`（格式敏感）、`verification_recovery`（验证恢复）、`repair`（修复）、`multi_step_ops`（多步操作）。12文件共享工作区，git验证。

**三种Harness条件：**
- **Light：** 两行提示（角色 + 裸任务描述），无格式说明、无作用域、无验证
- **Balanced：** 增加4步流程模板（计划→执行→检查→回应）+ 允许文件列表
- **Strict：** 增加6显式阶段（预检→计划→执行→验证→恢复→报告）+ 成功标准 + 验证规范 + 文件变更标记

**六模型四层级：** Gemini 2.5 Flash（前沿专有-chat）、Qwen3.5-122B（前沿推理，10B活跃参数）、GPT-OSS-120B（强开放）、Qwen3.5:2B / LLaMA 3.2 / Gemma4:e2B（约束级）

---

## 核心结果

### 1. Harness-复杂度悖论（前沿Chat模型）

Gemini 2.5 Flash：**Light 95.8% → Balanced 58.3%（-37.5pp）→ Strict 66.7%（-29.2pp）**。更复杂的harness反而降低了近40个百分点的成功率。**格式违规（format_violation）占全部Balanced+Strict失败的18/18**。根因：冗长的过程性提示诱导模型输出解释性散文而非要求的JSON格式——模型**有能力**完成，但抑制不住写散文的习惯。该悖论局限在`inspect_local`和`format_sensitive`类任务；`structured_edit`和`repair`仍保持100%。

### 2. U型非单调模式（前沿推理模型）

Qwen3.5-122B呈现U型曲线：Light 87.5% → Balanced 75.0%（谷底）→ Strict **91.7%（峰顶）**。更有趣的是，**Strict不仅最高分，还最低延迟**（23.3秒 vs Light 35.4秒、Balanced 38.5秒）。解释：显式成功标准与推理模型的chain-of-thought对齐，减少歧义；而Balanced形成"冲突信号"，被扩展思维放大。

### 3. 约束级异质性

三个截然不同的模式：
- **Qwen3.5:2B：** 倒U型（0% → 58.3% → 4.2%），Balanced提供最佳支架，Light完全崩溃（0%），Strict过载
- **LLaMA 3.2：** 全面低效（≤21%），缺乏基础指令跟随能力
- **Gemma4:e2B：** **91.7%贯穿所有三种harness**——仅20亿参数匹配强开放层稳定性，说明**指令微调质量 >> 参数规模**

### 4. 格式违规——系统性失败模式

六标签失败分类：format_violation（格式违规）、wrong_answer（回答错误）、wrong_file（改错文件）、missing_change（未修改）、unrelated_change（内容无关）、tests_still_fail（测试仍不过）。

**关键统计：** 在Balanced和Strict条件下，Gemini 2.5 Flash + Qwen3.5-122B共26次失败中，**格式违规占25/26**（其中10/10 + 8/8对应于Gemini，7/8对应于Qwen）。结论：能力足够的模型失败是**操作性**而非**认知性**的——它们理解任务，但被harness的格式和流程说明干扰，无法生成规范输出。而低能力模型则主要失败于wrong_file（改错文件），属能力限制。

---

## 实践意义

- **Frontier Chat模型：** Light最佳（成本最优、性能最高），Strict仅用于文件编辑
- **Frontier推理模型：** Strict最佳（降低错误率和延迟）
- **强开放模型：** Light ≈ Balanced（均95.8%）
- **约束级模型：** 不能一概而论——需要单独评估，指令微调质量比参数规模更关键
- 论文为**层级感知的Harness选择**提供了经验基础，建议agent评估先做harness-敏感性扫描
