---
title: openLLM四体与Hermes全景分析——关系·边界·互动
date: 2026-06-28
author: 军师祭酒
type: analysis
tags: [openllm, hermes, isa, ios, isn, iko, fata, 四体, 架构分析, 边界, 互动协议]
status: v1.0
---

# openLLM四体与Hermes全景分析

## 绪论

openLLM不是"一个系统"——它是四个系统（ISA/IO-S/ISN/IKO）的集合体，跑在Hermes平台上，遵循FATA路线图，目标是构建一个面向LLM的原生Harness Agent。

**核心矛盾**：四系统各自突飞猛进，但集成层缺失。每个系统都很强，但互相之间"认识但不熟悉"。

本文档从六个维度系统分析各系统的关系、边界和互动形式。

---

## 一、全景定位 · 一张图

```
┌──────────────────────────────────────────────────────────┐
│                    FATA 路线图（8关）                      │
│  "From Agent to AGI" — 研究方向 / 理论框架               │
└──────────────────────────────────────────────────────────┘
                            │ 指导
                            ▼
┌──────────────────────────────────────────────────────────┐
│                  openLLM（产品/愿景）                       │
│  面向LLM的原生Harness Agent — 四体的整合统一体            │
├─────────────────┬─────────────────┬──────────────────────┤
│  ISA v0.9.2     │  IO-S v0.3      │  ISN v2.x            │
│  记忆/认知系统   │  治理/操作系    │  技能系统            │
│  Brain+Cortex   │  22 syscalls    │  case_library        │
│  Gateway+Δ胶囊  │  Process状态机  │  50+ skills          │
├─────────────────┴─────────────────┴──────────────────────┤
│                     IKO（审计闸门）                       │
│  输出系统 — validate_tentacle · 包拯审计 · 七通道        │
├──────────────────────────────────────────────────────────┤
│                IDC（集成协调层·缺失中）                    │
│  统一信号总线 · 统一身份层 · 统一记忆层                   │
├──────────────────────────────────────────────────────────┤
│               Hermes Agent（底层平台）                    │
│  tools · skills · cron · channels · plugins · 运行时     │
└──────────────────────────────────────────────────────────┘
```

### 层级关系

| 层 | 角色 | 类比 |
|:--:|:----|:----:|
| **FATA** | 理论方向/路线图 | 宪法 |
| **openLLM** | 产品/目标 | 国家 |
| **ISA/IO-S/ISN/IKO** | 子系统 | 四个部委 |
| **IDC** | 四体协调者 | 总理办公室 |
| **Hermes** | 运行平台 | 物理国土 |

---

## 二、六系统定位详表

### 2.1 Hermes Agent

| 维度 | 内容 |
|------|------|
| **是什么** | Agent运行时平台。提供工具调用、skill管理、cron调度、多频道分发、plugin框架 |
| **管什么** | Agent怎么跑。tools·skills·cron·channels·plugins·memory |
| **不管什么** | Agent怎么思考（ISA的事）、怎么决策（IO-S的事）、技能边界在哪（ISN的事） |
| **当前状态** | 稳定。框架级的压缩器(2426行)、cron(20+ jobs)、plugins(20+)、channels(5) |
| **代码位置** | `.hermes/` — 运行时配置；`hermes/` — pip包中的框架代码 |

Hermes与四体的关系：Hermes是汽车底盘发动机，ISA/IO-S/ISN/IKO是四个不同的系统/模块。Hermes提供工具，四体提供决策。

**优势**：Hermes多年打磨，基础能力成熟。
**问题**：四体的能力没有很好地映射到Hermes的原语上——IO-S的syscall调用是独立于Hermes tool调用体系的。

### 2.2 ISA（记忆/认知系统）

| 维度 | 内容 |
|------|------|
| **是什么** | 认知架构。Brain(记忆引擎)+Cortex(感知)+Gateway(通信)+Δ胶囊(三层记忆) |
| **管什么** | Agent怎么记住、怎么通信、怎么感知。波扩散·ACK三角·认知涟漪·Dreaming |
| **不管什么** | Agent的权限边界（IO-S的事）、技能执行（ISN的事）、输出审计（IKO的事） |
| **当前状态** | v0.9.2。Brain 423行·27测试·波扩散成熟·Gateway HTTP+WS·44 commits |
| **瓶颈** | Web UI可用性缺失；Δ胶囊的共振协议（HELLO_TTL=24h）尚未与IO-S的session管理打通 |

ISA的核心贡献是**波扩散机制**——让Agent间的消息不是"点对点发送"，而是像声波一样传播。谁听谁收。

### 2.3 IO-S（治理/操作系统）

| 维度 | 内容 |
|:----:|------|
| **是什么** | Process状态机 + 22个syscall模块。从CARD→SIGNAL→DREAM→AGENT→PLANNING→...完整生命周期 |
| **管什么** | Agent怎么做决策。规划(planner)·审计(audit)·净化(sanitizer)·门控(gate)·检查点(checkpoint)·度量(conservation)·校准(calibrate) |
| **不管什么** | Agent怎么记忆（ISA的事）、技能怎么写（ISN的事）、输出格式（IKO的事） |
| **当前状态** | **v0.3。22模块/3400行。今天从790行到3400行，增量全部有测试覆盖。** |
| **核心syscall** | 见附录A |

IO-S是今天最大的变数——从6个syscall/790行裂变为22个syscall/3400行。它的进化速度远快于其他三个系统。

### 2.4 ISN（技能系统）

| 维度 | 内容 |
|:----:|------|
| **是什么** | 人格化标准化功能模块系统。Skill/ZA/SA三层架构。三层信息分级 |
| **管什么** | Agent会什么技能。Skill创建·skill审计·skill优化·skill退役 |
| **不管什么** | Agent怎么决策执行（IO-S的事）、认知记忆（ISA的事）、输出格式（IKO的事） |
| **当前状态** | v2.x。case_library三层·50+ skills·四原型覆盖·外部标杆萃取管线 |
| **瓶颈** | L5协议定义未工程化；批量萃取自动化管线待建 |

ISN的独特之处在于它将skill视为一个**人格化功能模块**——不是零散的工具，而是有身份、有边界、有生命周期的标准化单元。

### 2.5 IKO（输出/审计系统）

| 维度 | 内容 |
|:----:|------|
| **是什么** | 输出闸门。validate_tentacle.py（八触须校验）+ 包拯审计 + Asset Manifest + 七通道 |
| **管什么** | 输出合规。模板引擎·格式签名·人工审核闸门·审计轨迹 |
| **不管什么** | 输出怎么生成（ISN的事）、认知判断（ISA的事）、决策过程（IO-S的事） |
| **当前状态** | 工程化阶段。validate_tentacle.py是硬关卡——不合规不进索引。<br>包拯审计已实现no_agent脚本化。 |
| **核心原则** | 不合规不进索引。不审计不发布。 |

IKO是四个系统中"最不性感但最关键"的——没有它，IO-S的syscall再强、ISA的记忆再深、ISN的技能再多，产出的文档要是格式混乱、审计不全，整个系统就不可靠。

### 2.6 openLLM（产品愿景）

| 维度 | 内容 |
|:----:|------|
| **是什么** | 四体的统一体。面向LLM的原生Harness Agent |
| **管什么** | 四体的整合协调。不是"另一个系统"——是四个系统的**总和** |
| **不管什么** | 四个系统各自的具体实现细节 |
| **当前状态** | 概念层。IDC正在推动集成层建设 |
| **FATA路线图** | 8关：基础能力→Agent通信→自我边界→递归理解→世界建模→自我修改→安全对齐→多模态 |

---

## 三、边界 · 谁不做什么

这是最关键的维度——**四体之间的边界不是"能力上限"，是"我不做什么"的契约。**

### 边界矩阵

```
                ISA            IO-S             ISN            IKO
ISA           —            不做进程管理     不做技能定义   不做格式校验
IO-S     不做认知推理      —              不做技能注册   不做内容签名
ISN      不做记忆存储     不做权限决策      —            不做发布调度
IKO      不做信号传播     不做过程审计     不做技能优化    —
```

### 详细边界

| 边界声明 | 谁承诺 | 内容 |
|----------|:------:|------|
| **ISA不做权限** | ISA | ISA不检查agent的行动边界。ISA只管"这条信号被发送了"不管"该不该发送"。权限check去IO-S。 |
| **ISA不做技能** | ISA | ISA不定义agent会什么技能。ISA只感知到"有一条消息到达了"——具体消息是什么技能调的，ISA不知道。 |
| **IO-S不做记忆** | IO-S | IO-S不记录"历史"。IO-S只记录"当前状态"和"当前决策"。记忆去ISA的Δ胶囊。 |
| **IO-S不做认知** | IO-S | IO-S的planner只分解任务、分配任务、回溯优化——不"理解"任务内容。理解是ISA的事。 |
| **ISN不做运行时** | ISN | ISN定义skill怎么写、怎么审计、怎么优化——不关心skill怎么执行。执行去IO-S。 |
| **ISN不做存储** | ISN | ISN的case_library只记录元数据（技能名、版本、审计状态）。具体数据存ISA的Δ胶囊。 |
| **IKO不做生成** | IKO | IKO只校验格式、审计内容、调度发布——不生成内容。生成是ISN+IO-S+ISA共同的事。 |
| **IKO不做推理** | IKO | IKO不执行任何推理。它的审计规则是确定的、无状态的、可验证的。 |

### 边界违背案例

| 案例 | 违背 | 后果 | 修复 |
|:----:|:----:|:----:|:----:|
| IO-S的planner试图"理解"任务语义 | 越界到ISA | 规划质量依赖LLM理解力，不是IO-S的职责 | planner只分解不解释 |
| ISA记录权限决策 | 越界到IO-S | 权限日志和认知日志混在一起 | 权限决策入IO-S audit，不入Δ胶囊 |
| ISN在skill文件里定义运行时行为 | 越界到IO-S | skill文件变得像脚本，失去标准化 | ISN只定义接口，不定义实现 |
| IKO试图"优化"输出内容 | 越界到ISN | 审计者变成了内容修改者 | IKO只通过/不通过，不改内容 |

---

## 四、互动 · 怎么通信

### 4.1 当前互动方式

目前四体之间的通信主要通过**三条路径**：

```
路径A：Hermes skill调用（成熟）
  Agent → 调Hermes skill → skill内部调ISA/IO-S/ISN/IKO
  → 当前主力互动方式
  → 优点：成熟、稳定
  → 缺点：skill强制回合制，不能做异步、流式交互

路径B：ISA波扩散（半成熟）
  ISA Gateway → 波扩散 → 所有Agent被动收信
  → 适用场景：系统通知、广播事件
  → 优点：一对多、异步
  → 缺点：还没和IO-S的syscall体系打通

路径C：IO-S syscall（新路线）
  Agent → kernel.dispatch → IO-S syscall → 返回结果
  → 适用场景：规划、审计、度量等决策行为
  → 优点：统一的调用框架
  → 缺点：还只有IO-S自己的syscall，ISA/ISN/IKO都没接入
```

### 4.2 理想互动模式

```
            ISA(记忆/认知)
           ↗   ↑   ↖
   波扩散  ←──┼──→  波扩散
           ↓   │   ↓
    IO-S(治理)  ──→  ISN(技能)
           ↓       ↓
          IKO(输出/审计)
```

**四体间的通信协议应该是"混合型"：**

| 场景 | 通信方式 | 发起方 | 接收方 |
|:----:|:--------:|:------:|:------:|
| 决策类 | IO-S syscall | IO-S | 全体 |
| 事件类 | ISA波扩散 | ISA | 全体 |
| 请求类 | Hermes tool call | Agent | 任意系统 |
| 通知类 | Δ胶囊共振 | 任意系统 | 全体 |
| 审计类 | IKO校验 | IKO | IO-S |

### 4.3 与Hermes的互动

**Hermes是底盘，不是上层建筑。**

```
Agent请求
    │
    ▼
┌────── Hermes ──────┐
│  tools · skills    │
│  cron · channels   │  ← 基础设施层
└──────┬─────────────┘
       │ 调Hermes tool 或 直接调syscall
       ▼
┌────── openLLM ─────┐
│ ISA  IO-S  ISN  IKO│  ← 决策/认知/技能层
└─────────────────────┘
       │
       ▼
    返回结果给Agent
```

**关键原则**：Hermes不知道ISA/IO-S/ISN/IKO的存在。Hermes只提供工具（tools/skills/cron/channels）——四体是Agent自己决策调用的逻辑层。

### 4.4 IO-S v0.3的独特位置

IO-S v0.3成为四体中最"工具化"的系统——它的22个syscall是直接可调用的函数。ISA还没有类似的统一调用接口，ISN也是。

这意味着IO-S有可能成为**四体互动的默认入口**——不是因为它比ISA/ISN/IKO更重要，是因为它的架构最方便做集成。

---

## 五、依赖链

### 启动依赖

```
Hermes（必须先启动 — 平台）
    │
    ▼
ISA（第二启动 — 提供通信基础）
    │
    ▼
IO-S（第三启动 — 提供治理框架）
    │
    ▼
ISN（第四启动 — 提供技能系统）
    │
    ▼
IKO（最后启动 — 提供输出闸门）
```

### 运行时数据流

```
用户请求
  → ISA感知（Cortex接收信号）
  → IO-S决策（planner分解→权限check→分配syscall）
  → ISN执行（skill匹配→skill调用）
  → IKO审计（validate_tentacle检查输出合规）
  → IO-S回传（结果装配→检查点保存）
  → ISA记忆（Δ胶囊记录事件）
```

### 四体间数据流依赖（2026-06-28实测状态）

```
ISA的波扩散 → IO-S的process状态 → ISN的skill选择 → IKO的输出校验
    ✅ 独立运作      ✅ 22 syscall         ⚠️ 未接入IO-S    ✅ validate_tentacle
```

**实测缺口**：ISN的skill选择和IO-S的syscall调用之间还没有标准接口——IO-S的planner不知道ISN有哪些可用skill。

---

## 六、现状评估

### 6.1 各系统成熟度

```
Hermes  ████████████████ 100%  稳定·生产级
ISA     ██████████░░░░░  65%   v0.9.2·波扩散成熟·Web UI缺失
IO-S    ████████████░░░  75%   v0.3·22 syscall·测试覆盖·进化最快
ISN     █████████░░░░░░  55%   v2.x·50+ skills·三层架构·L5协议待工程化
IKO     █████████░░░░░░  55%   validate_tentacle·包拯·七通道·自动化待全量
openLLM ████░░░░░░░░░░░  25%   概念层·IDC协调中
```

### 6.2 核心矛盾

1. **IO-S进化太快，其他三体没跟上**——IO-S从790行到3400行只用了一天。ISA/ISN/IKO还是原来的节奏。

2. **ISN和IO-S之间无标准接口**——IO-S的planner和audit不知道ISN有哪些可用skill。skill选择靠Agent在prompt里手写。

3. **集成层（IDC）缺工程化**——IDC的角色已定义（四体协调者），但没有对应的代码/配置/自动化cron。IDC还是一个"找人聊天"的角色。

4. **Hermes和IO-S的syscall未打通**——Hermes自己有tool调用体系，IO-S有自己的syscall调用体系。两者独立存在，Agent需要知道"什么时候调Hermes tool，什么时候调IO-S syscall"。

### 6.3 下一件最该做的事

**先打通IO-S和ISN之间的标准接口。**

IO-S有22个syscall，ISN有50+个skill。两者之间现在是"手工接线"——Agent在对话里写"帮我调planner分解任务"或者"帮我写一个xxx skill"。应该有一个标准的skill_discovery syscall，让IO-S的planner能在执行时查询可用skill列表。

这个接口一旦建成，IO-S就真正成了四体的"运行时引擎"，ISN就真正成了四体的"技能仓库"。其他三体可以通过IO-S调用ISN，ISN可以通过IO-S注册新技能。

---

## 附录A：IO-S v0.3 syscall全景

```
syscall/               Process状态机
├── card.py            CARD        — 卡片CRUD
├── signal.py          SIGNAL      — 信号收发
├── dream.py           DREAM       — 梦境引擎
├── agent.py           AGENT       — Agent生命周期
├── planner.py         PLANNING    — 任务分解 (PEEU L13)
├── async_planner_executor.py       — 异步调度
├── hindsight_loop.py              — 回溯循环
├── audit.py                       — 包拯审计
├── checkpoint.py                  — GPU检查点 (Concordia L14)
├── evidence.py                    — 证据引导 (AutoPass L3)
├── sanitizer.py                   — 内容净化 (RoleConfusion L6)
├── gate_sync.py                   — 协作门控 (SSVP L11)
├── pipeline.py                    — ISA三层管线 (Layered L1-L2)
├── cache_strategy.py              — KV缓存 (Kamera L7)
├── self_evolve.py                 — 自进化 (SelfHarness L10)
├── self_compact.py                — 自压缩 (Kamera+SelfCompact L7-L8)
├── bits_metric.py                 — 比特度量 (AgenticCompressor L12)
├── team_scale.py                  — 团队规模 (MAS-PromptBench L11.b)
├── gamma_monitor.py               — 全局Γ (Contagion L5-L6)
├── prospective_memory.py          — 前瞻记忆 (TriggerBench L8-L9)
├── economy.py                     — 经济层 (Web4 L15)
├── conservation_law.py            — 守恒律 (跨论文)
└── calibrate.py                   — 偏差校准 (阿瑞斯)
```

---

## 附录B：金句

> **Hermes是底盘，IO-S是方向盘，ISA是导航仪，ISN是工具箱，IKO是质检员。**

> **四体的边界不是"做不了"，是"不该做"。IO-S可以做认知——但那会变成ISA。ISA可以做权限——但那会变成IO-S。**

> **openLLM不是一个"新系统"——它四个系统之间的空间。**

> **四体至今最大的进步在IO-S，最大的缺口在ISN↔IO-S接口，最大的未解在IDC工程化。**
