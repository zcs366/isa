# 踩坑记录：补强最弱层的方法论——ddgs替代web_search

> 日期：2026-06-28 · 类型：lesson · 关键词：ddgs, web_search替代, 搜索可靠性, 工具替代原则

---

## 踩坑描述

web_search(Hermes内置，DuckDuckGo后端)全线超时，被确定为搜索管线最弱层。如何补强？

## 根因分析

web_search和ddgs使用同一个DuckDuckGo后端，但实现路径不同：
- **ddgs** = Python库，直接调DuckDuckGo API，无中间层
- **web_search** = Hermes内置实现，经过Hermes层（可能有代理/超时/rate-limit问题）

**问题在实现层，不在DuckDuckGo本身。**

## 解法

**不是修web_search，是用ddgs替代。**

实测对比（2026-06-28）：

| 查询类型 | ddgs | web_search |
|----------|:----:|:----------:|
| 英文：octopus distributed nervous system | ✅ 3/3 | ❌ 超时 |
| 中文：章鱼 分布式 神经系统 | ✅ 3/3 | ❌ 超时 |
| 学术：octopus vertical lobe connectome | ✅ 3/3 | ❌ 超时 |
| **总计** | **100%** | **0%** |

## 教训

| # | 教训 | 来源 |
|---|------|------|
| 1 | **补强最弱层=换实现，非修实现** | ddgs直接调API绕过Hermes层，比web_search更可靠 |
| 2 | **内置工具≠最优工具** | web_search是Hermes内置但不可靠，ddgs是独立库但可靠 |
| 3 | **同一个后端不同路径=不同结果** | DuckDuckGo后端没问题，Hermes实现层有问题 |
| 4 | **多场景实证是选型唯一标准** | ddgs在英文/中文/学术三类查询中100%命中 |

## 最佳实践

1. 搜索工具选型基于多场景实证（非单一场景）
2. 内置工具不可靠时，优先用独立Python库替代
3. Tier分级必须反映实际可靠性，非理论可靠性
4. 搜索失败是正面信号——暴露弱点，触发改进

## 关联

- search-pipeline skill v2.3.2（ddgs升Tier 0.5+）
- jiak卡片：fata-gates, izu-research-pipeline, anthropic-safety-spectrum
- 决策记录：tentacles/decision/
