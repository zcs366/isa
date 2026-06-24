# Reconstruct Phase 2 — LLM精确推理协议

> ISA Brain的两段式记忆重建的第二阶段。
> Phase 1(0 token)已完成: cue→tag→content正向遍历 + content→tag→cue反向遍历。
> Phase 2(LLM精确推理): 对Phase 1的粗召回结果做精确验证和合成。

## 架构

```
用户查询
  ↓
Phase 1: reconstruct(query, use_llm=False)
  ├── cue提取 → _forward_traverse → 粗召回候选
  ├── _backward_traverse → 反向发现
  └── 写 RECALL: type=reconstruct_phase2_request
  ↓
Phase 2: delegate_task (子Agent)
  ├── 读 RECALL 最新 phase2_request
  ├── 逐卡读全文 → 验证相关性
  ├── 合成连贯答案
  └── 写 RECALL: type=reconstruct_phase2_result
  ↓
用户下次会话: 自动注入 Phase 2 结果
```

## Phase 2 子Agent Prompt 模板

```
你是ISA Brain的精确推理模块。

查询: {query}

Phase 1 粗召回卡片:
{for each candidate: card_id, summary, cues, tags, source}

Phase 1 反向发现:
{for each backward: card_id, summary, shared_tags, new_cues}

任务:
1. 逐卡判断——这张卡真的回答查询吗？
   - YES: 直接相关，提供了查询所需信息
   - PARTIAL: 部分相关，提供了背景或上下文
   - NO: 不相关，Phase 1误召回

2. 找缺口——查询要求的信息，哪些在现有卡片中不存在？
   - 列出具体的信息缺口
   - 不要编造不存在的信息

3. 合成——如果多张卡拼起来能回答，合成一段连贯答案
   - 标注每段信息来自哪张卡片
   - 如果信息不足，诚实说明

4. 返回结构化JSON:
{
  "answer": "合成的答案（可含不确定性标注）",
  "confidence": 0.0-1.0,
  "source_cards": [
    {"card_id": "...", "relevance": "YES/PARTIAL/NO", "contribution": "..."}
  ],
  "gaps": ["缺失信息1", "缺失信息2"],
  "suggested_new_cues": ["可能相关但未被Phase 1捕获的关键词"]
}
```

## RECALL事件格式

### Phase 2 请求 (brain.py写入)
```json
{
  "type": "reconstruct_phase2_request",
  "query": "用户的自然语言查询",
  "query_cues": ["提取的关键词"],
  "candidate_card_ids": ["card1", "card2"],
  "backward_card_ids": ["card3", "card4"],
  "estimated_tokens": 150,
  "timestamp": "ISO时间"
}
```

### Phase 2 结果 (子Agent写入)
```json
{
  "type": "reconstruct_phase2_result",
  "query": "原始查询",
  "answer": "合成答案",
  "confidence": 0.85,
  "source_cards": [...],
  "gaps": [...],
  "suggested_new_cues": [...],
  "tokens_used": 0,
  "timestamp": "ISO时间"
}
```

## 调用方式

### 方式1: 手动触发 (当前推荐)
```python
# 在Hermes会话中
brain = Brain("军师")
result = brain.reconstruct("ISA的波扩散引擎怎么工作?", use_llm=True)
# Phase 1结果立即返回, Phase 2写入RECALL
# 然后delegate_task处理Phase 2
```

### 方式2: Cron自动处理 (未来)
```
每15分钟扫描RECALL中未处理的phase2_request
→ delegate_task处理
→ 写回phase2_result
```

### 方式3: 子Agent直接调用 (当前实现)
子Agent读RECALL → 读卡片 → 推理 → 写回RECALL

## 容错

- Phase 2失败不阻断Phase 1结果返回
- Phase 2超时(5分钟)→标记为stale，下次重试
- 子Agent可以返回abstention: "现有卡片不足以回答此查询"
- Phase 2结果是增量资产，不影响Phase 1的0-token路径

## 与守恒律的关系

Phase 1 + Phase 2 = 守恒律的工程实例:
- Phase 1: 0 token, 粗召回, 可能漏 (低压缩率, 高召回)
- Phase 2: N token, 精确验证, 不漏 (高压缩率, 高精度)
- d×r×log₂(L)≈K_W: 你可以要速度或精度，但不能同时要两者
