# 综合PAL · 18篇论文驱动 Hermes + openLLM 进化

> 签发人：军师 · 日期：2026-06-28 · 关键词：综合PAL, 18篇论文, 17层, Hermes, openLLM, ISA, IO-S, ISN, IKO

## 一、总纲

18篇论文覆盖17层设计要求。每篇论文都对Hermes Agent或openLLM四系统（ISA/IO-S/ISN/IKO）有直接工程启示。本PAL综合所有发现，形成从底层到顶层的完整进化路线。

### 18篇论文的核心信号（按影响排序）

| # | 论文 | 影响信号 | 目标系统 | 优先级 |
|:-:|------|---------|:--------:|:------:|
| 1 | **PEEU** | 低层原子技能≠高层规划→IO-S需规划层 | IO-S | 🔴 P0 |
| 2 | **Contagion** | 同模型异质profile传染弱(γ=0.14-0.30) | IKO | 🔴 P0 |
| 3 | **Concordia** | GPU-resident checkpoint 219×加速 | ISA | 🔴 P0 |
| 4 | **SEB** | 执行强制+零常设凭证 | IO-S | 🔴 P0 |
| 5 | **Role Confusion** | 风格覆盖标签→表达隔离 | ISN | 🟡 P1 |
| 6 | **SSVP** | 全广播同步幻觉+34%→门控同步 | ISN | 🟡 P1 |
| 7 | **Agentic Compressor** | 375 bits/seq验证器价值 | IKO | 🟡 P1 |
| 8 | **Self-Harness** | 三阶段自改进闭环 | ISN | 🟡 P1 |
| 9 | **APEX** | 三轴协同+90%、L3单独-10% | ISN | 🟡 P1 |
| 10 | **HarnessSensitivity** | 非单调性→层级感知选型 | ISN | 🟡 P1 |
| 11 | **Layered-Security** | 三层防御ASR 71.4%→11.3% | ISA | 🟡 P1 |
| 12 | **MACR** | 语义熵置信度+冲突消解 | ISA | 🟡 P1 |
| 13 | **AutoPass** | 证据引导的Agent推理循环 | ISA | 🟡 P1 |
| 14 | **Kamera** | 位置不变KV缓存复用45×加速 | ISA | 🟡 P1 |
| 15 | **Self-Compacting** | 规则门控压缩30-70%降本 | ISA | 🟡 P1 |
| 16 | **TriggerBench** | PM认知悬崖r=-0.91 | ISA | 🟢 P2 |
| 17 | **MAS-PromptBench** | 团队>4优化转负 | ISN | 🟢 P2 |
| 18 | **Web4** | MCP+x402+EIP-8004经济层 | IKO | 🟢 P2 |

---

## 二、P0 — 本周（4项）

### P0-1: IO-S规划层 + 执行强制（来自PEEU+SEB）

**已部分完成**：Phase 1-2（Process状态机扩展 + planner syscall + AsyncPlannerExecutor）
**需补充**：

| 子项 | 来源 | 内容 | 预估 |
|------|------|------|:----:|
| a. hindsight经验闭环 | PEEU | 完成 `complete_with_hindsight` 在子Agent编排中的实际接入 | 2h |
| b. cap_policy planner条目 | SEB | 在cap_policy.json中加 `planner` 资源类型，受控bypass | 0.5h |
| c. 包拯 audit.plan_quality | PEEU+SEB | 实现包拯审计syscall，检查plan结构完整性 | 2h |
| d. 零常设凭证原则 | SEB | 确认IO-S dispatch不缓存任何执行凭证 | 0.5h |

**总工期**：~5h · **可并行**：a∥b→c→d

### P0-2: 评估治理（来自Contagion）

Contagion Networks的核心反直觉发现：同模型异质profile传染γ=0.14-0.30，交叉模型传染γ=0.85-1.3。这意味着Hermes当前的交叉模型合议模式（deepseek-chat/MiMo混合）本身就在高风险区。

| 子项 | 内容 | 预估 |
|------|------|:----:|
| a. 同模型profile切换 | 子产/韩信/鲁班/萧何/子贡统一用同一模型+异质system prompt | 0.5h |
| b. 委员会制度 | 评估任务k=3 committee，压制72.4%传染 | 1h |
| c. 传染矩阵监测 | 定期计算Γ矩阵，发现级联态立即告警 | 2h |

**总工期**：~3.5h · **可并行**：a∥b→c

### P0-3: GPU-resident Checkpoint设计（来自Concordia）

Concordia的核心：219×加速，0.53% SM占用，~1.5s双GPU恢复。将jiak持久层升级为region注册+delta-checkpoint。

| 子项 | 内容 | 预估 |
|------|------|:----:|
| a. jiak region注册接口 | Process[pid]作为checkpoint region的设计 | 1h |
| b. 哨兵升级为恢复执行器 | 哨兵检测到崩溃后触发region恢复 | 2h |
| c. AOF日志格式 | 借鉴Concordia的append-only log | 1h |

**总工期**：~4h · **无法并行**（依赖关系紧密）

### P0-4: 证据引导Agent循环（来自AutoPass）

AutoPass的四Agent证据引导循环（Score→Analysis→Reasoning→Evaluation）是Agent推理的模式升级。

| 子项 | 内容 | 预估 |
|------|------|:----:|
| a. 引入Evidence字段 | 每个tool call的返回附Evidence置信度评分 | 1h |
| b. 推理→评估闭环 | 在子Agent执行后增加评估Agent | 2h |
| c. 证据不足降级 | Evidence置信度低时自动触发重试或换方案 | 1.5h |

**总工期**：~4.5h · **可并行**：a→b∥c

---

## 三、P1 — 本周（6项）

### P1-1: ISN内容净化×协作协议（来自Role Confusion+SSVP）

| 子项 | 来源 | 内容 | 预估 |
|------|------|------|:----:|
| a. 表达隔离 | Role Confusion | web_fetch/cnscrape结果在注入前剥离语气/修辞 | 2h |
| b. 门控同步 | SSVP | ISN通信协议改用CDS门控（τ=0.25），禁止全广播 | 3h |
| c. 风格探针 | Role Confusion | 在jika中嵌入CoTness/userness探针 | 3h |

**总工期**：~8h · **可并行**：a∥b→c

### P1-2: ISN自进化体系（来自Self-Harness+APEX+HarnessSensitivity）

三篇论文形成完整闭环：机制(Self-Harness)×全面性(APEX)×边界条件(HarnessSensitivity)。

| 子项 | 来源 | 内容 | 预估 |
|------|------|------|:----:|
| a. 三阶段自改进 | Self-Harness | 弱点挖掘→Harness提案→双集验证 | 3h |
| b. 三轴协同 | APEX | Harness审查+原则蒸馏+工作流拓扑 | 4h |
| c. 层级感知选型 | HarnessSensitivity | 模型能力≠越强越好的自动检测 | 2h |

**总工期**：~9h · **可并行**：a∥b→c

### P1-3: ISA三层防御+冲突消解（来自Layered-Security+MACR）

| 子项 | 来源 | 内容 | 预估 |
|------|------|------|:----:|
| a. 输入筛查L1 | Layered-Security | 工具返回数据进入前做注入签名检测 | 1h |
| b. 权限上下文L2 | Layered-Security | ISA Gateway组装prompt时做层级权限标注 | 2h |
| c. 输出审计L3 | Layered-Security | LLM输出前检测指令漂移 | 2h |
| d. 语义熵置信度 | MACR | 多源冲突时计算语义熵，低置信度触发重新检索 | 3h |

**总工期**：~8h · **可并行**：a∥b∥c→d

### P1-4: KV缓存复用（来自Kamera+SelfCompact）

| 子项 | 来源 | 内容 | 预估 |
|------|------|------|:----:|
| a. 位置不变缓存 | Kamera | 在ISA中实现Relocate+Position-Invariant补丁 | 3h |
| b. 规则门控压缩 | SelfCompact | 固定间隔压缩改为规则门控触发 | 2h |

**总工期**：~5h · **串行**（依赖关系紧密）

### P1-5: 比特度量体系（来自Agentic Compressor）

| 子项 | 内容 | 预估 |
|------|------|:----:|
| a. 验证器边际价值 | 计算每次LLM调用的信息增益(bits) | 2h |
| b. codelength监控 | 持续测量系统组件的比特贡献 | 2h |

**总工期**：~4h

### P1-6: Self-Compacting上下文压缩（来自SelfCompact）

| 子项 | 内容 | 预估 |
|------|------|:----:|
| a. Rubric规则模板 | 不同任务类型的压缩规则模板 | 2h |
| b. 早触发策略 | 上下文增长曲线的自动触发压缩 | 1.5h |

**总工期**：~3.5h

---

## 四、P2 — 本月（5项）

### P2-1: 前瞻记忆管理（来自TriggerBench）
- PM认知悬崖100K处：实现前瞻记忆的自动降级和提醒机制
- 推理预算探针(r=-0.91)：用PM Acc反向推测推理容量余量

### P2-2: 经济层接入（来自Web4）
- MCP Tunnels三方共识的Web4协议兼容层
- 双轨计量基准线建立

### P2-3: 团队规模优化（来自MAS-PromptBench）
- 子Agent团队>4时自动拆分为2个并行小组
- 结构化协议优先于自由协议

### P2-4: 全局评估治理（来自Contagion）
- 全系统Γ矩阵定期监控
- 级联态自动切换至委员会模式

### P2-5: d×r×log(L)≈K_W 守恒律工程化验证
- 在IO-S中嵌入守恒律实时测量
- 17层覆盖度与守恒律参数的对位验证

---

## 五、总工期和关键路径

```
P0-1: IO-S规划层+执行强制  ─── 5h  ──┐
P0-2: 评估治理             ─── 3.5h ──┤
P0-3: GPU-checkpoint设计   ─── 4h   ──┤── 并行 → 本周
P0-4: 证据引导Agent循环    ─── 4.5h ──┘
P1-1~P1-6: 6项           ─── ~38h ── 下周
P2-1~P2-5: 5项           ─── ~20h ── 本月

总工期预估: P0 ~17h · P1 ~38h · P2 ~20h · 总计 ~75h
```

## 六、产出物索引

| PAL | 路径 |
|:---:|------|
| 📜 本综合PAL ✅ | `tentacles/pal/2026-06-28_pal_综合18篇论文进化Hermes_openLLM.md` |
| 📜 原有PAL存档 | `tentacles/pal/2026-06-28_pal_L13-L15论文精读后行动计划.md` |
| 🔬 研究分析 | `tentacles/analysis/` (18篇) |
| 📝 精读笔记 | `tentacles/notes/` (18篇) |
