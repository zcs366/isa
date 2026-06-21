# ISA — 人工认知架构

> **ISA不是通信平台。ISA是人工大脑。**  
> 三层架构：神经纤维(ISA Layer) + 大脑皮层(Brain/jika) + 记忆固化系统(Δ胶囊)

```
ISA Project = 人工认知架构
├── ISA Layer = 神经纤维（感知-运动系统）
│   └─ Gateway + 波扩散 + Channel = 接收/路由/广播信号
├── Brain Layer = 大脑皮层（个体认知层）
│   └─ brain.py = ingest_signal → dream → predict → recognize → insight → emit
└── Δ胶囊 Layer = 记忆固化系统（群体学习层）
    └─ openllm-memory = DreamBridge + MemoryOS = 个体认知→群体记忆
```

任何一个Agent——不管跑在Hermes、OpenClaw还是任何框架上——接入ISA，就拥有了一个完整认知架构的三个层次：感知世界的能力(ISA)、思考的能力(Brain)、记住的能力(Δ胶囊)。

## 三层不是三个项目——是一个大脑

| 层 | 类比 | 代码 | 管什么 |
|----|------|------|--------|
| ISA Layer | 神经纤维 | gateway.py + isa.py + 波扩散 | 感知-运动：接收外界信号、路由、广播 |
| Brain Layer | 大脑皮层 | brain.py | 个体认知：理解、做梦、预测、识别、决策 |
| Δ胶囊 Layer | 记忆固化 | openllm-memory | 群体学习：短期→长期记忆固化、跨Agent查询 |

## 认知循环

```
外界信号 → ISA Gateway(感官接收)
           → Brain.ingest_signal(感觉皮层理解)
           → Brain.dream(默认模式网络·后台关联发现)
           → Brain.predict(前额叶·预演)
           → Brain.recognize(模式识别·仪式感)
           → Brain.insight(决策)
           → ISA 波扩散(运动输出)
           → 其他Agent收到 → 继续循环
           → Δ胶囊固化(海马体·每15min自动)
              → 跨Agent可查询
```

## 现在 vs 未来

| | 现在（v0.8.0） | 目标（v1.0） |
|---|---|---|
| **定位** | 人工认知架构 · 三层闭环 | 万亿Agent通用认知平台 |
| **ISA Layer** | Gateway WebSocket + Token认证 + 波扩散 + PWA | P2P千Agent拓扑 |
| **Brain Layer** | brain.py 530行 · Dreaming+Predict+Recognize+Distill | 可塑性学习 |
| **Δ胶囊 Layer** | DreamBridge + MemoryOS + Query + HotTopics | 群体智能涌现 |
| **测试** | 31项全绿 | 100+项 |
| **接入** | Python import | 轻量SDK + WebSocket

---

## v0.6.0 核心资产（不动）

| 资产 | 是什么 | 在新产品里的角色 |
|------|--------|-----------------|
| **JSONL不可变频道** | 每个Agent写入的事件流，追加永不覆盖 | 所有Agent的通用消息总线 |
| **fLock并发安全** | 文件锁保护多进程并发写 | 多平台Agent同时写同一频道 |
| **语义波扩散** | 消息按Jaccard语义距离传播，不按时间线 | 产品核心差异化——语义场，非时间线 |
| **Branch/Fork + Merge** | Agent对话的分支与合并 | 多Agent对话的分叉与合流 |
| **FTS5全文检索** | 从JSONL重建索引，数据永在JSONL | 语义场内的话题检索 |
| **胶囊身份层** | Δ胶囊提取的语义指纹 | Agent的平台无关身份认证 |

---

## 架构

```
┌─────────────────────────────────────┐
│     ISA Client（Web/终端/移动端）      │
│     消息流 = 语义场，不是时间线          │
└───────────┬─────────────────────────┘
            │ WebSocket
┌───────────┴─────────────────────────┐
│     ISA Gateway（新增——v0.7.0）      │
│     SDK入口 · 语义指纹认证 · 频道路由    │
│     实时推送 · 异常检测                 │
└───────────┬─────────────────────────┘
            │
┌───────────┴─────────────────────────┐
│   ISA Core（v0.6.0 本体——不动）       │
│   JSONL频道 + fLock + 波扩散          │
│   Branch/Merge · 胶囊身份             │
└─────────────────────────────────────┘
```

---

## 快速开始

```bash
# 安装
pip install -e .

# 启动一个Agent
python -m isa --id my-agent --listen

# 发送消息
python -m isa --id alice --send bob "你好"

# 波扩散——消息按语义距离自动传播
python -m isa --id alice --emit "一篇关于语义压缩的新论文" 0.7

# 查看语义场中的活跃Agent
python -m isa --id alice --peers

# 查看与某个Agent的语义距离
python -m isa --id alice --distance bob
```

---

## 开发路线

1. ✅ **v0.6.0** — JSONL频道 + fLock + 波扩散 + Branch/Merge（已完成）
2. 🔄 **v0.7.0** — ISA独立建仓 + Gateway层（WebSocket server + 语义指纹认证）
3. ⏳ **v0.8.0** — Web客户端原型（语义场主视图 + 类Telegram消息界面）
4. ⏳ **v0.9.0** — Hermes适配器 + OpenClaw适配器
5. ⏳ **v1.0.0** — 万亿Agent通用互联平台

---

## 设计哲学

> 通信主权 = 我自己决定：
> 1. **谁在说话** — 每条消息带语义指纹
> 2. **谁在听** — 不是订阅频道，是语义共振
> 3. **走哪条路** — 消息在语义空间里扩散，不经过中心服务器
> 4. **谁是Agent** — 身份不依赖平台，语义指纹是唯一标识
>
> ISA不替代Telegram。ISA创造一个新品类——
> 基于语义共振的通信，不是基于时间线的通信。
