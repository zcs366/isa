# Sovereign Execution Broker: Enforcing Certificate-Bound Authority in Agentic Control Planes
> 签发人：军师 · 日期：2026-06-28 · 关键词：执行代理（SEB）、证书绑定权限、自主控制平面、零常设凭证、OpenKedge、可撤销执行、范围化身份、运行时强制

## 一、论文基本信息

- **标题：** Sovereign Execution Broker: Enforcing Certificate-Bound Authority in Agentic Control Planes
- **作者：** Jun He, Deying Yu（OpenKedge.io）
- **arXiv ID：** 2606.20520v2
- **提交日期：** 2026年6月19日（v2）
- **篇幅：** 19页，6图，10表
- **分类：** cs.CR（密码学与安全）；cs.AI（人工智能）；cs.DC（分布式并行计算）；cs.LG（机器学习）
- **核心贡献：** 提出SEB（主权执行代理），作为证书绑定的自主控制平面的运行时强制边界。SEB填补了从**提案准入（SAB签发证书Ω）**到**运行时执行（基础设施变更）**之间的空白，确保自主智能体绝不持有常设的生产环境变更凭证。
- **核心原则：** "智能体及其包装器必须持有**零常设变更凭证**"——所有变更权限都在执行时刻实时签发、范围限定、可撤销。

## 二、核心方法

### 2.1 三层架构（OpenKedge栈）

| 层 | 组件 | 功能 |
|----|------|------|
| L1 | SQA（语义法定数保障） | 验证提议动作的语义正确性 |
| L2 | SAB（主权保障边界） | 签发签名的准入证书Ω |
| **L3** | **SEB（主权执行代理）** | **在变更执行时刻强制证书绑定** |

### 2.2 证书结构（Ω）

SAB签发的证书Ω包含以下字段：

```
Ω = (cid, C, E_admit, T_valid, P_ver, ρ_rev, nonce, issuer, σ_SAB)
```

其中：
- `cid`：合约标识符
- `C = (op, target, params, constraints, risk_level)`：执行合约
- `E_admit`：准入时刻的证据状态（快照）
- `T_valid`：证书有效期窗口
- `P_ver`：准入时刻的策略版本
- `ρ_rev`：准入时刻的撤销纪元
- `nonce`：单次使用的防重放值
- `σ_SAB`：SAB签名

### 2.3 七步验证管线

SEB的`Execute(Ω, req, St, Platform)`接口执行以下验证：

| 检查 | 输入 | 失败记录 |
|------|------|---------|
| Φsig 签名验证 | Ω, σ_SAB | D: reject |
| Φmatch 合约匹配 | req, Ω, C | D: reject |
| Φtime 时间窗口 | T_valid | D: reject |
| Φpolicy 策略版本 | P_ver, P_active | D: reject/re-admit |
| Φrev 撤销检查 | ρ_rev, ρ_active | D: fail closed |
| Φdrift 状态漂移 | E_admit, St | D: reject/re-admit |
| Φreplay 重放防护 | cid, nonce, L | D: reject |

**形式化验证谓词：**
```
V = Φsig ∧ Φmatch ∧ Φtime ∧ Φpolicy ∧ Φrev ∧ Φdrift ∧ Φreplay ∧ Scopeable(C, Platform)
```

**关键语义：** 所有7项检查必须全部通过。任何单项失败都生成签名的DECISIONRECORD写入只追加账本。

### 2.4 范围化执行身份

```
ID_exec = MintIdentity(C, Ω, target, scope, T_valid, ρ_rev)
```

| 维度 | 强制机制 |
|------|---------|
| 操作（Action） | 原生IAM/RBAC操作 |
| 资源（Resource） | 原生ARN、命名空间、对象名 |
| 参数（Parameters） | 原生条件或代理代理/准入 |
| 时间（Time） | STS有效期 + SEB有效性检查 |
| 证书（Certificate） | 会话标签、准入元数据、账本绑定 |
| 策略（Policy） | SEB验证 P_ver = P_active |
| 撤销（Revocation） | SEB验证 ρ_rev = ρ_active |

**凭证时长：** Kubernetes 60秒（使用TokenRequest投影令牌），AWS STS 900秒（最低支持）。

### 2.5 绕过防护部署模式

**AWS模式：**
- SCP策略禁止高风险变更，除非主体=代理角色或代理签发会话（带标签：`seb:cid`, `seb:nonce`, `seb:issuer`, `seb:risk`）
- Agent角色有**权限边界**，排除生产环境变更API
- 仅代理角色可调用`sts:AssumeRole`进入目标执行角色

**Kubernetes模式：**
- Agent ServiceAccount：只读（无create/update/patch/delete）
- Broker ServiceAccount：唯一授权变更动词的账户
- Validating Admission Webhook拒绝不带`seb.openkedge.io/cid`和`seb.openkedge.io/nonce`标注的变更请求

### 2.6 原型实现

| 维度 | 细节 |
|------|------|
| 语言 | Go v1.21 |
| 代码量 | 4,200 LoC（不含测试） |
| 副本 | 3（HA模式） |
| 数据库 | PostgreSQL v15（Amazon RDS db.r6g.xlarge） |
| 密码学 | Go标准库 `crypto/ed25519` |
| 撤销缓存 | 本地sync.Map，5秒轮询，5秒TTL |
| 部署 | AWS EKS v1.28（m6i.xlarge worker） |

### 2.7 安全模型

**可信组件：** SEB执行环境、SAB签名密钥、SEB签名密钥、全局撤销纪元服务、云提供商身份提供商、目标平台IAM/RBAC/准入控制、账本只追加属性。

**不可信/容错：** Agent运行时和提示上下文、各语义验证器、本地操作员/管理员、实时目标状态观察（最终一致性）。

**防御的威胁向量：** 代理绕过、过期证书重放、请求-证书不匹配、TOCTOU状态漂移、过期纪元/撤销绕过、过度范围凭证滥用、代理分区。

## 三、关键结果

### 3.1 验证微基准（5,000次试验）

| 组件 | p50（ms） | p99（ms） |
|------|----------|----------|
| Ed25519签名验证 | 0.021 | 0.043 |
| 状态漂移查询 | 7.2 | 18.4 |
| 撤销缓存查询 | 0.003 | 0.009 |
| 全管线（已缓存撤销） | 7.5 | 19.1 |
| 全管线（未缓存撤销） | 12.3 | 31.7 |

→ p50全管线延迟7.5ms，远低于典型API调用超时，证明SEB可嵌入生产路径而不引入显著开销。

### 3.2 端到端延迟（100次试验）

| 场景 | 平均延迟（ms） | 标准差（ms） |
|------|--------------|------------|
| AWS STS凭证签发 | 892 | 124 |
| Kubernetes TokenRequest | 78 | 15 |
| 决策记录写入 | 4.2 | 0.8 |
| 结果记录写入 | 4.5 | 0.9 |
| **端到端（AWS）** | ~910 | ~130 |
| **端到端（K8s）** | ~95 | ~18 |

### 3.3 重放防护

| 并发客户端 | 请求/秒 | 拒绝率（正确模式） | 拒绝率（无nonce） |
|-----------|---------|-----------------|------------------|
| 1 | 200 | 0.0% | 42.0% |
| 5 | 1,000 | 0.0% | 78.9% |
| 10 | 2,000 | 0.9% | 91.9% |
| 50 | 10,000 | 19.7% | 99.5% |

→ Nonce保留机制有效防止重放攻击。在正常负载下（≤1,000请求/秒）零错误率。

### 3.4 定理证明（安全保证）

**定理1（无未经授权的生产变更）：** 在SEB部署假设下——(1) 无Agent运行时持有常设变更凭证；(2) 目标API仅接受来自授权变更主体（代理角色+代理签发会话）的变更；(3) 紧急直通身份在自主Agent路径之外——对于任意由Agent提议的变更请求，如果该请求执行后改变了生产系统状态，则必然存在一个对应的有效证书Ω，且经过SEB全部7项检查。

**推论1（强制执行非绕过性）：** Agent运行时无法绕过SEB直接变更生产系统——因为所有变更API都强制要求SEB签发的凭证，Agent不持有这些凭证。

**定理2（过期证书的自动失效）：** 若证书Ω已过期（当前时间 > T_valid.expiry），则SEB的Φtime检查失败，生成DECISIONRECORD，拒绝执行。

## 四、与17层的关联（L4-L6: 正确性边界）

这篇论文与**第4层（动作正确性边界/动作边界）**、**第5层（评估正确性边界/评估边界）**、**第6层（内容正确性边界/内容边界）**都有深刻关联，但最核心的映射在**L4**。

### L4 动作边界（Action Correctness Boundary）
- **SEB就是L4的运行时实现。** 第4层定义了"哪些动作是可以安全执行的"，SEB提供了具体的安全强制机制：通过7步验证管线确保每个动作都经过授权、在有效期内、未被撤销、无状态漂移、无重放。
- **零常设凭证原则**是L4的核心设计模式——Agent运行时（非确定性推理过程）不应直接持有生产环境凭据，这解决了L4中长期存在的"谁可以做什么"的权限管理问题。
- **范围化身份**将L4的粗粒度权限拆解为7个维度的精细控制（操作、资源、参数、时间、证书、策略、撤销）。

### L5 评估边界（Evaluation Correctness Boundary）
- SQA和SAB承担L5的部分功能——评估提议动作的语义正确性。但SEB标志着从"评估"到"执行"的跨越：评估阶段（SQA/SAB）判断"这个提案是否有意义"，执行阶段（SEB）判断"这个提案现在是否仍可安全执行"。
- SEB的`Φdrift`（状态漂移检查）是L5评估在时间维度上的延伸——准入时的评估结论可能在执行时刻已过时，需要重新验证。

### L6 内容边界（Content Correctness Boundary）
- SEB的`Φmatch`（合约匹配检查）确保执行请求的内容与经过评估的证书内容一致，防止Agent在SQA/SAB评估后篡改操作参数。
- Decision Record和Outcome Record构成完整的审计轨迹，为事后内容正确性验证提供不可抵赖的证据。

### 对17层架构的补充启示
- **Epoch化撤销状态**解决了跨层撤销的一致性问题——一个集成撤销纪元的全局机制可以同时使L4-L6的多个证书/授权失效
- **Fail-closed语义**（不可达撤销服务时自动拒绝）是安全强制的黄金法则，17层边界设计中也应默认fail-closed
- **凭证最短时长原则**（K8s 60秒/AWS STS 900秒）是时间维度边界管理的具体实践

## 五、与Hermes Agent的关联

### 直接映射场景

Hermes Agent在以下场景可以直接借鉴SEB架构：

1. **Tool执行安全层：** Hermes的tool调用机制目前是"提案-执行"直通模式。引入SEB式的轻量级证书检查层，可为每个tool调用添加签名验证、时间窗口、nonce防重放等保障。

2. **子Agent权限隔离：** 当Hermes生成子Agent执行任务时，子Agent不应持有常设权限。应在执行时刻通过类似SEB的MintIdentity签发范围化临时权限。

3. **PLUR记忆操作的审计：** 对PLUR的learn/forget/修改操作可以增加SEB风格的DecisionRecord，确保每次记忆变更都有签名记录和前置验证。

### 设计启示

- **Hermes Plugin系统的安全边界：** Plugin调用可以引入类似SEB的验证管线——至少包含签名验证(Φsig)、合约匹配(Φmatch)、时间窗口(Φtime)
- **跨会话撤销：** 借鉴SEB的epoch化撤销机制，PLUR的engram可以引入ρ_rev纪元，支持批量撤销/更新
- **Tool调用的nonce防重放：** 针对Hermes工具调用链路，在关键操作上引入nonce防重放保护
- **Broker模式在Hermes Studio中的运用：** Hermes Studio的LAN peer通信可引入SEB式的签发-验证模型

### 不足之处
- SEB的原型目前仅覆盖AWS和K8s平台，未覆盖其他基础设施
- 论文缺少对Broker自身被攻破时的安全分析
- 4,200 LoC的原型在真实生产环境中需扩展更多平台适配器

## 六、结论与待办

### 核心结论
1. **SEB填补了关键空白：** SAB签发证书但无法保证运行时执行安全，SEB提供了7步验证的强制边界
2. **零常设凭证原则正确：** Agent运行时不应持有任何生产环境凭据，所有权限应在执行时刻动态签发
3. **性能可接受：** p50全管线7.5ms（AWS STS约910ms端到端），对生产路径几乎无影响
4. **绕过防护可部署：** AWS SCP + K8s Webhook两种模式均实现强制执行
5. **形式化安全保证：** 定理1-2证明了无未授权变更和过期自动失效两个关键安全属性

### 待办事项
- [ ] 评估Hermes Agent tool调用链路引入SEB轻量级验证的可能性
- [ ] 设计Hermes Plugin的安全加载/执行证书机制
- [ ] 探索PLUR记忆操作增加epoch化撤销支持
- [ ] 评估在Hermes Studio的LAN peer通信中引入签发-验证模式
- [ ] 关注OpenKedge后续关于SEB在更多平台（GCP、Azure）的扩展
