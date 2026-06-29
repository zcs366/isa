# Concordia: JIT-Compiled Persistent-Kernel Checkpointing for Fault-Tolerant LLM Inference — GPU-resident恢复范式

> 签发人：军师 · 日期：2026-06-28 · 关键词：Concordia, 恢复层, GPU-resident, JIT-compiled handler, lock-free ring buffer, L14, 持久内核检查点

## 一、论文基本信息

| 项 | 内容 |
|---|------|
| **标题** | Concordia: JIT-Compiled Persistent-Kernel Checkpointing for Fault-Tolerant LLM Inference |
| **arXiv ID** | [2606.23521](https://arxiv.org/abs/2606.23521) |
| **分类** | cs.DC (Distributed, Parallel, and Cluster Computing) / cs.LG |
| **日期** | 2026-06-22 |
| **核心主张** | LLM推理的容错需要**GPU驻留执行上下文**——checkpoint hook必须在设备同步点上运行，观察二进制kernel，恢复时不把host CPU放在critical path |

## 二、核心方法

### 2.1 三类GPU State

| 类别 | 描述 | 变化模式 |
|------|------|---------|
| Immutable model weights | 大、极少变化 | 加载后静态 |
| KV-cache & scheduler state | 追加密集型、动态 | 每token变化 |
| LoRA adapters & optimizer state | 小型可变区域 | 适配期间变化 |

### 2.2 为什么应用级KV Logging不够

> "生产serving栈不暴露统一KV写入路径。PagedAttention将逻辑token映射到动态分配的物理cache块；融合attention kernel可能更新多个cache区域；LoRA或测试时适配更改单独的parameter pages；通信库在模型代码之外改变collective buffers。"

Concordia使用**page-level tracking**作为透明恢复契约。

### 2.3 持久内核运行时

**核心**：持久kernel持续处理来自共享队列的任务。预留**1个worker block** = **0.53% SM占用**（RTX PRO 6000）。

**故障模型**：应用kernel、GPU ranks、collective communication中的fail-stop故障。持久checkpoint worker是可信控制环。如果worker心跳停止，GPU被视为丢失——从CXL/DRAM中最后提交的AOF记录恢复。

**三个组件**：
1. **Lock-free ring buffer**：设备映射内存中的64-128字节任务描述符
2. **Single persistent kernel**：启动时创建，保持驻留
3. **Operator table**：设备驻留数组，按operator ID索引，支持通过版本计数器热插拔

### 2.4 Host端API

| 函数 | 描述 |
|------|------|
| `init(capacity, tpb)` | 初始化运行时，分配队列 |
| `fuse()` | 融合等待中的checkpoint任务 |
| `register(region, flags)` | 注册GPU内存区域 |
| `request_checkpoint(flags)` | 请求检查点 |
| `append_to_aof(data)` | 追加日志 |
| `recover(region_list)` | 恢复 |

### 2.5 JIT-Compiled Delta-Checkpoint Handler

每个注册的region类型绑定JIT编译的handler：
- **KV-block scanner**：扫描dirty pages
- **Adapter-page scanner**：检测LoRA参数变化
- **Recovery applier**：恢复时应用delta

这些handler通过`operator table`热插入到持久kernel中。

## 三、关键结果

### 3.1 性能数据

| 测试 | CPU方式 | GPU方式 | 加速比 |
|------|---------|---------|-------|
| 256MB区域dirty page检测 | 106.65ms (Python/NumPy) | 0.04-0.53ms | **up to 219×** |
| CPU full copy (256MB) | 4.72ms | — | — |
| GPU comparison | — | 0.04ms | — |
| Checkpoint trigger提交 | — | 亚微秒 | — |
| 持久kernel SM占用 | — | **0.53%** | 极低 |
| 双GPU原型恢复 | — | **~1.5s** | — |

### 3.2 核心洞察

CPU侧透明diffing的耗时与区域大小×CPU内存带宽成正比；GPU侧diffing的耗时与区域大小×HBM带宽加上dirty bytes/PCIe成正比。**GPU侧方法在256MB区域上比CPU侧快219倍**。

## 四、与Hermes Agent的关联

### 4.1 核心痛点映射

| Hermes当前问题 | Concordia的解法 |
|---------------|----------------|
| sub-agent失败时无状态保留，只能从头跑 | GPU-resident checkpoint保存KV cache/scheduler状态 |
| jiak卡片写入是event-sourced但推理上下文无checkpoint | 每个注册region有JIT编译的delta-checkpoint handler |
| cuda失败→hook重新加载→工作丢失 | lock-free ring buffer + persistent kernel永开executor |
| 哨兵仅做存活检测，无恢复执行层 | ~1.5s双GPU恢复，AOF日志追加到CXL/DRAM |

### 4.2 与Execution-State Capsules (2606.12485, 06-21)的对偶

| 维度 | Execution-State Capsules (06-21) | Concordia (06-27) |
|------|-------------------------------|-------------------|
| 位置 | **端侧** (on-device graph-bound) | **云侧** (GPU-resident) |
| 机制 | 图约束的状态胶囊 | 持久kernel + lock-free ring buffer |
| 恢复粒度 | 函数/子任务级 | GPU state region级 |
| 适用场景 | 移动端/边缘推理 | 数据中心GPU推理 |
| **合起来** | **端云两侧的Agent状态恢复范式** | |

### 4.3 与L14（恢复层）的精确对位

| 设计要求 | Concordia覆盖 | Hermes当前 |
|---------|:------------:|:----------:|
| 崩溃后自动恢复 | ✅ GPU-resident checkpoint | ❌ 哨兵仅检测 |
| 状态不丢失 | ✅ delta-checkpoint + AOF | ❌ 从头跑 |
| 恢复不阻塞主流程 | ✅ lock-free ring buffer | ❌ |
| 低开销监控 | ✅ 0.53% SM占用 | ✅ 哨兵低开销 |

## 五、结论与待办

### 5.1 对Hermes的三个具体启示

1. **jiak持久层升级**：把sub-agent state看作需要checkpoint的LLM state region，借鉴Concordia的region注册+JIT handler模式
2. **恢复执行层**：哨兵之后应该有一个"恢复执行器"——从RECALL快照恢复sub-agent上下文
3. **lock-free设计**：章鱼wink的crash recovery可移植Concordia的lock-free ring buffer模式

### 5.2 待办项

| 优先级 | 行动 |
|--------|------|
| P1 | 将Concordia的region注册模式引入jiak持久层设计 |
| P1 | 设计哨兵→恢复执行器的管线（从检测到恢复） |
| P2 | 评估lock-free ring buffer在章鱼wink中的适用性 |
