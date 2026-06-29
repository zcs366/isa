# AutoPass: Evidence-Guided LLM Agents for Compiler Performance Tuning
> 签发人：军师 · 日期：2026-06-28 · 关键词：编译器优化、多智能体、证据驱动、LLVM性能调优、工具正确性

## 一、论文基本信息
- **标题：** AutoPass: Evidence-Guided LLM Agents for Compiler Performance Tuning
- **arXiv ID：** 2606.20373
- **日期：** 2026年6月18日提交
- **作者：** Zepeng Li, Jie Ren, Zhanyong Tang, Jie Zheng, Zheng Wang
- **领域：** cs.SE（软件工程）、cs.AI（人工智能）

## 二、核心方法
提出**AutoPass框架**——基于LLM多智能体的证据驱动编译器性能调优系统。核心创新在于打开编译器黑箱，让LLM直接查询编译器内部优化状态和中间表示（IR）。四智能体协同工作：

1. **Score Agent（评分智能体）**：扫描源码目录，构建跨过程调用图，提取IR原生特征（代码块数/循环数/调用数/条件分支数），筛选高影响函数并输出完整LLVM IR。

2. **Analysis Agent（分析智能体）**：从符号名/元数据推断语义线索；利用编译器诊断（`-Rpass`/`-Rpass-missed`/`-Rpass-analysis`）获取优化缓存/未命中等信息，输出归一化JSON。

3. **Reasoning Agent（推理智能体）**：两阶段决策——首轮结合目标约束与分析摘要制定初始优化方案；后续轮次根据运行时反馈剪枝无效变换、调整参数。含确定性修复与验证（语法检查/模式验证/编译检查）。

4. **Evaluation Agent（评估智能体）**：编译、验证、剖析每个候选方案，收集执行时间、硬件计数器、更新后的编译器备注。接受标准：候选方案均值运行时间 < 当前最优。失败时回退到最优管线，最终无改善则返回-O3。

**核心设计原则**：不将编译器视为黑箱——查询编译器优化备注和LLVM IR快照，暴露变换效果。

## 三、关键结果
- **x86-64平台**：几何平均加速比**1.043×**（超越-O3），cBench 1.059×、CoreMark 1.137×、LULESH 1.102×
- **ARM64平台**：几何平均加速比**1.117×**，cBench 1.139×、PolyBench 1.016×、CoreMark 1.069×
- 超越PGO、CSSPGO、AutoFDO、OpenTuner等所有基线
- 74个优化pass，序列最长107个pass，3轮迭代（3个候选方案）
- 以DeepSeek-V3.2为主LLM后端（对比测试含ChatGPT-4o、Qwen3、Gemini 3 Flash）
- 广泛基准：cBench（31）、PolyBench（30）、CoreMark、MiniFE、LULESH

## 四、与17层的关联（L1-L3: 正确性治理）
- **L1（输入正确性）**：Score Agent对源码的IR特征提取和对高影响函数的筛选，确保只有关键代码段进入优化决策管道——这本质上是输入层级的数据质量和相关性治理。
- **L2（决策正确性）**：Reasoning Agent的迭代优化决策（初始提案→反馈→剪枝→调参）对应决策层级的正确性治理。确定性修复与验证机制（语法/模式/编译三关）确保决策可执行。
- **L3（工具正确性）**：Evaluation Agent的编译-剖析-反馈闭环直接对应工具层正确性治理——每次工具调用（编译）的结果都被严格验证，无效或退化方案被自动回退。硬件计数器的引入提供了远超"编译成功/失败"二值的细粒度工具效果评估。

## 五、与Hermes Agent的关联
- AutoPass的四智能体编排模式（评分→分析→推理→评估）与Hermes Agent的思考-行动-反思循环高度对应，可视为编译器优化领域的Hermes架构范本。
- 证据驱动（Evidence-Guided）理念——借助编译器内部信号而非纯黑箱搜索——与Hermes Agent强调的可回溯、可验证决策原则一致。
- Evaluation Agent的"回退到最优"和"最终回退到-O3"策略，可作为Hermes Agent执行链中安全回退机制的参考模式。
- 硬件计数器作为细粒度工具反馈源的理念可扩展：Hermes Agent可对任何工具调用附加多维度成功率/质量指标，而非仅二值成功/失败。
- 确定性修复与验证阶段（语法→模式→编译）可作为Hermes Agent工具调用验证管线的结构化模板。

## 六、结论与待办
- **结论**：AutoPass代表了一个重要范式转变——从黑箱搜索到白箱证据驱动的编译器优化。其多智能体编排、迭代反馈闭环、确定性验证链的设计，使其在x86和ARM上均稳定超越现有方法（含PGO）。训练无关的设计意味着极低的迁移成本。
- **待办**：① 将AutoPass的评估-回退机制借鉴到Hermes Agent的工具调用安全回退设计中；② 研究编译器内部信号（IR/优化备注）作为Agent环境观测的通用模式；③ 评估在Hermes Agent中引入多维度工具质量指标（类似硬件计数器）的可行性；④ 探索AutoPass的确定性验证管线在Agent代码生成场景的应用。
