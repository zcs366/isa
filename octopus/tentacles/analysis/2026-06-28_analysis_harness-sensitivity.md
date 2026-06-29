# It's Not the Capability: Harness Sensitivity Is Non-Monotone Across LLM Agent Tiers
> 签发人：军师 · 日期：2026-06-28 · 关键词：Harness敏感性、非单调、层级效应、HEAT-24、失败分类学

---

## 一、论文基本信息

- **标题：** It's Not the Capability: Harness Sensitivity Is Non-Monotone Across LLM Agent Tiers
- **作者：** 本文作者团队
- **来源：** arXiv:2605.26731 [cs.AI, cs.CL]
- **核心问题：** 模型能力越强，是否越不需要复杂的 harness 结构？（即"单调逆假设"是否成立？）
- **核心发现：** **不成立。** Harness 敏感性跨模型层级是非单调的，取决于模型类型（chat vs. reasoning）而非参数规模。
- **实验规模：** 432 次运行 × 6 个模型 × 3 种 harness 条件 × 24 任务（HEAT-24 基准）
- **核心贡献：** ① 否定单调逆假设 ② 提出 Harness-Complexity Paradox（前缘聊天模型）③ 提供层级感知的 Harness 选择指南

---

## 二、核心方法

### 2.1 三种 Harness 条件

| 条件 | 复杂度 | 内容 |
|------|--------|------|
| **Light** | 极简 | 两行提示（角色 + 原始任务指令）。无格式/作用域/验证规范。 |
| **Balanced** | 适中 | 四步流程模板（Plan → Execute → Check → Respond）+ 允许文件列表 |
| **Strict** | 最复杂 | 六阶段模板（Preflight → Plan → Execute → Verify → Recover → Report）+ 成功标准 + 验证规范 + 文件变更标记 |

### 2.2 模型层级设计

| 层级 | 模型 | 类型 |
|------|------|------|
| **Frontier-Proprietary** | Gemini 2.5 Flash | 前缘闭源聊天模型 |
| **Frontier-Reasoning** | Qwen3.5-122B-A10B | 前缘开源推理模型 |
| **Strong-Open** | GPT-OSS-120B | 强开源通用模型 |
| **Constrained** | Qwen3.5:2B / LLaMA 3.2 / Gemma4:e2B | 受限参数模型 |

### 2.3 HEAT-24 基准

- 24 个任务 × 6 类别（各 4 个）
  - inspect local / structured edit / format sensitive / verification recovery / repair / multi step ops
- 工作空间：12 个合成文件（YAML, JSON, Python, Markdown, CSV, changelog）+ git 仓库
- 验证：确定性二元验证器（git diff, JSON 解析, 测试执行）
- 度量：VTSR（Valid Task Success Rate，严格的可解析+正确输出率）

---

## 三、关键结果

### 3.1 核心数据：各模型在各 Harness 下的 VTSR（%）

| 模型 | 层级 | Light | Balanced | Strict |
|------|------|-------|----------|--------|
| Gemini 2.5 Flash | Frontier-Proprietary | **95.8** | 58.3 | 66.7 |
| Qwen3.5-122B-A10B | Frontier-Reasoning | 87.5 | 75.0 | **91.7** |
| GPT-OSS-120B | Strong-Open | **95.8** | **95.8** | 87.5 |
| Qwen3.5:2B | Constrained | 0.0 | **58.3** | 4.2 |
| LLaMA 3.2 | Constrained | 16.7 | 4.2 | 20.8 |
| Gemma4:e2B | Constrained | **91.7** | **91.7** | **91.7** |

### 3.2 四大关键发现

#### 发现①：Harness-Complexity Paradox（前缘聊天模型）

> Gemini 2.5 Flash：Light（95.8%）→ Balanced（58.3%，−37.5pp）→ Strict（66.7%，−29.2pp）

- 复杂 harness 引入**格式违规**为主要失败模式（10/10 Balanced 失败；8/8 Strict 失败）
- 悖论仅出现在**格式敏感型任务**和**本地检查型任务**（Light 下 100% → 复杂 harness 下 0%~25%）
- 结构化编辑/修复任务在所有 harness 下保持 100%

#### 发现②：非单调模式（前缘推理模型）

> Qwen3.5-122B：Light（87.5%）→ Balanced（75.0%，下降）→ Strict（91.7%，回升）

- Strict 下同时获得**最低延迟**（23.3s，vs Light 35.4s，Balanced 38.5s）
- 严格的显式约束**缩小了推理模型的搜索空间**，提效降错

#### 发现③：受限层级的极端异质性

- **Gemma4:e2B（2B 参数）：** 三个 harness 下均 91.7%，匹配 Strong-Open 层级的稳定性——**参数规模不是能力的可靠代理**
- **Qwen3.5:2B：** 倒U型：Light 0% → Strict 4.2% → Balanced 58.3%——极简则灾难，极繁则过载
- **LLaMA 3.2：** 整体 ≤ 21%，缺乏基线指令遵循能力——不适合 workspace 编辑任务

#### 发现④：失败分类学

| 标签 | 描述 | 主导出现于 |
|------|------|----------|
| **Format violation（格式违规）** | 输出不可解析 | 能力模型 + 复杂 harness |
| Wrong answer | 可解析但答案错误 | 罕见 |
| Wrong file | 修改了允许集外的文件 | 受限模型 + Light harness |
| Missing change | 未检测到文件修改 | 罕见 |
| Unrelated change | 正确文件但错误内容 | 从未观察到 |
| Tests still fail | 代码变更未通过测试 | 罕见 |

> **"格式违规是复杂 harness 对能力模型引入的主要失败模式：26 个失败中 25 个"**

---

## 四、与 17 层的关联（L10-L10.b: 自进化）

### 核心映射

本论文为 **L10.b（自进化）** 提供了**关键的边界条件分析**——进化的方向不能是盲目的：

| 17层概念 | 本文贡献 |
|---------|---------|
| **L10 自演化不能无约束** | 复杂 harness 对特定模型可能有**反效果** |
| **L10.b 机制必须感知层级** | 自进化算法需要根据模型类型选择进化方向 |
| **进化的"边界"高度敏感** | 格式约束边界对 chat 模型有害，对 reasoning 模型有益 |
| **参数 ≠ 能力** | Gemma4:e2B（2B）表现优于许多更大模型——这挑战了"能力梯度的单调性"假设 |

### 对 17 层的具体贡献

1. **自进化需要层级感知（Tier-Aware）：** 不能一刀切地增加 harness 复杂度——对某些模型增加约束反而是退化
2. **非单调性纳入进化边界条件：** L10.b 的"不退化约束"需要考虑到——从 Balanced 到 Strict 对某些模型是"进化"（Qwen3.5-122B: +16.7pp），但对其他模型可能是"退化"（Gemini 2.5 Flash: +8.4pp 但离 Light 的 95.8% 仍有差距）
3. **格式违规是自进化需要重点解决的风险：** 如果 self-harness 增加结构，必须确保格式约束不会成为能力模型的瓶颈
4. **参数规模 ≠ 层级的充分刻画：** 17 层中的层级划分需要考虑 instruction-tuning 质量，而不仅仅是参数规模

### 实践指南（映射到 17 层）

| 17层 Tier | 推荐的 Harness 策略 | 依据 |
|-----------|-------------------|------|
| 前缘聊天型（如 Gemini 2.5 Flash） | Light，仅结构化编辑任务可适当增加 | Paradox：复杂格式导致 -29~38pp |
| 前缘推理型（如 Qwen3.5-122B） | Strict | 显式约束缩小搜索空间，降低延迟 |
| 强开源型 | Light 或 Balanced | 等效性能，Strict 反而 -8.3pp |
| 受限-高指令质量（如 Gemma4:e2B） | 任意 | 指令调优质量 > 参数规模 |
| 受限-中指令质量（如 Qwen3.5:2B） | Balanced | Light 灾难性，Strict 过载 |
| 受限-低指令质量（如 LLaMA 3.2） | 不推荐 | 不适合 workspace 任务 |

---

## 五、与 Hermes Agent 的关联

| 维度 | 本文贡献 | Hermes 应用 |
|------|---------|------------|
| **Harness 设计** | 不同层级需要不同复杂度 | Hermes profile 中的 skill/prompt 复杂度应根据模型动态调整 |
| **失败分类学** | 6 类失败模式 | Hermes 的 `plur_feedback` 可记录更精细的失败标签（format_violation, wrong_file 等） |
| **非单调性警示** | 增加 harness ≠ 提升 | Hermes 的 Self-Harness 实验必须验证增加约束不降低 chat 类模型的 VTSR |
| **格式约束设计** | 核心风险是"格式违规" | Hermes 的输出解析器应设计容错机制（fallback parsing） |
| **层级感知** | 相同的 harness 对不同模型效果相反 | Hermes 的多 Agent 场景中，不同子 Agent 可能需要不同的 harness 复杂度 |

---

## 六、结论与待办

### 结论

1. **单调逆假设被否定：** 能力越强的模型不一定越不需要 harness——关键是模型类型而非能力
2. **非单调性是核心发现：** Qwen3.5-122B 呈现 U 型模式（Light 87.5% → Balanced 75.0% → Strict 91.7%）
3. **格式违规是头号杀手：** 26 个复杂 harness 失败中 25 个源自格式不可解析——设计 harness 时必须重点解决
4. **参数规模不是能力代理：** Gemma4:e2B（2B）在受限层级中远超 LLaMA 3.2 和 Qwen3.5:2B
5. **层级感知的 Harness 设计是自进化的前提条件：** 任何 Self-Harness 系统必须能感知"当前模型属于哪个层级/类型"

### 待办

1. ✅ 理解非单调性发现及其对自进化的影响
2. ✅ 分析失败分类学（格式违规主导模式）
3. ✅ 提取层级感知的 Harness 设计指南
4. 🔲 在 Hermes 中实现"层级检测"模块：自动识别当前模型属于 chat/reasoning/constrained
5. 🔲 设计 Hermes 的 Self-Harness 接收规则时，加入"格式违规风险"的惩罚项
6. 🔲 基于 HEAT-24 框架构建 Hermes 的 harness 敏感性测试套件
