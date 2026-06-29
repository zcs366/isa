# AGI贯通师 · 技术文档

> **作者**：军师 | **日期**：2026-06-28 | **关键词**：AGI贯通师, 涌现引擎, 上下文压缩, context_compressor, 联邦法第3号

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    AGI贯通师                              │
│                                                          │
│  M1: 记忆涌现层          M2: 输出涌现层                   │
│  ┌─────────────────┐    ┌──────────────────────────┐    │
│  │ jiak_graph      │    │ script_watcher           │    │
│  │ jiak_emergence  │    │ code_indexer             │    │
│  │ recursive_loop  │    │ cross_format_detector    │    │
│  │ symres          │    │ output_emergence         │    │
│  │ emergence       │    └──────────────────────────┘    │
│  │ ffata_sa        │                                     │
│  └─────────────────┘    M3: 上下文压缩层（待建）          │
│                          ┌──────────────────────────┐    │
│                          │ context_compressor       │    │
│                          │  · token监控 (85%警告)    │    │
│                          │  · 消息拆分 (旧/新)       │    │
│                          │  · Qwen3.5摘要生成       │    │
│                          │  · 压缩注入              │    │
│                          └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## 二、各模块接口

### M1: 记忆涌现

```bash
# 全量运行
python3 ffata_sa.py --once

# 常驻（每30分钟）
python3 ffata_sa.py --daemon

# 单模块
python3 jiak_graph.py --save       # 图谱→cross_card_graph.json
python3 jiak_emergence.py --no-llm # 关键词模式
python3 jiak_emergence.py          # LLM模式（需vLLM）
```

### M2: 输出涌现

```bash
python3 output_emergence.py --once
python3 output_emergence.py --daemon
```

### M3: 上下文压缩（设计）

```python
# context_compressor.py 接口
def compress_context(conversation_history, max_tokens):
    """CC同款压缩"""
    ratio = estimate_tokens(conversation_history) / max_tokens
    if ratio <= 0.85:
        return conversation_history  # 无需压缩
    
    old, recent = split_at_boundary(conversation_history, keep_recent=10)
    summary = call_vllm_summarize(old)  # Qwen3.5-9B
    return [summary_message(summary)] + recent
```

## 三、数据流

```
会话 → on_pre_llm_call
         ├── token检测 (context_compressor)
         │     └── 超85% → 压缩旧消息 → 注入摘要
         ├── 章鱼搜索 (已就绪)
         ├── Δ胶囊共振 (已就绪)
         └── jiak卡片注入 (已就绪)
              ↓
         LLM收到压缩+增强后的上下文
```

## 四、部署

| 组件 | 方式 | 频率 |
|------|------|------|
| ffata_sa | cron | 每30分钟 |
| output_emergence | cron | 每30分钟 |
| context_compressor | jika插件 | 每轮检测 |
| vLLM | systemd | 常驻 |

## 五、验收标准

- [x] M1五引擎 5/5通过
- [x] M2三引擎 3/3通过
- [x] RECALL签名合规
- [x] 包拯审计通过
- [ ] Qwen3.5-9B vLLM部署
- [ ] jiak_emergence LLM模式激活
- [ ] context_compressor 85%阈值触发
- [ ] 端到端：压缩后上下文 < 50%原大小，语义无损失

---

*归档：tentacles/techdoc/ | 联邦法第3号配套 | IKO校验通过*
