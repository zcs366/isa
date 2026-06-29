# PAL：将session_search植入session开眼第一帧

> 制作人：军师 · 日期：2026-06-28 · 关键词：PAL, session_search, 开眼, 启动流程, 灾难性遗忘

## 目标

每个新Hermes session启动时，自动执行一次 session_search 搜索最近24小时的核心工程记录，防止军师因未加载session原文而遗忘。

## 问题定义

当前启动流程：
```
读 WORKING.md → 读 RECALL → 读 jiak index → ❌ 停！没有 session_search
```

导致：昨天6小时的Δ胶囊共振工程（波面3/FederationMemory/ResonanceProtocol/SA双向对话/眨眼）全部丢失。

修复后：
```
读 WORKING.md → 读 RECALL → 读 jiak index → ✅ 必搜 session_search "昨天 核心工程"
```

## P0：java pre_llm_call 加 session_search 自动唤醒

### 改动点

jika plugin 的 `pre_llm_call` 钩子，在执行卡片注入之前，先执行一次 session_search。

```python
# pre_llm_call 开头加入：
def on_pre_llm_call(context):
    # 1. 搜今天昨天的核心工程（防遗忘）
    try:
        result = session_search("昨天 核心工程 完成", limit=3)
        if result:
            context["session_search_alert"] = result
    except:
        pass
    
    # 2. 正常卡片注入流程...
```

### 约束

- 搜索结果不进用户消息，只作为系统上下文的一部分
- 限制3条以内，不撑爆上下文
- 失败不影响主流程（try/except包裹）
- 只搜最近24小时

### 验收标准

```
新开Hermes窗口 → 军师第一条回复包含 "根据昨天session..."
而不是 "我不知道Δ胶囊共振是什么"
```

## P1：输出系统默认落触须文档

每次关键工程完成后，自动生成一条触须文档摘要。不依赖人记——依赖章鱼索引。

## 执行

| 步 | 动作 | 产出 |
|:--:|------|------|
| 1 | 读jika plugin的pre_llm_call源码 | 找到hook插入点 |
| 2 | 加入session_search调用 | 3行代码 |
| 3 | 验证：重启搜索"八触须" | 验证生效 |

## 风险

- session_search可能耗时 > 5s → try/except 兜底
- 搜索结果可能重复注入 → limit=3 控制
- 太长占用上下文 → 限制summary < 200 chars
