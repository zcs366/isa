# 决策记录：ddgs替代web_search成为Tier 0.5+

> 日期：2026-06-28 · 类型：decision · 关键词：ddgs, web_search替代, 搜索可靠性, Tier分级

---

## 背景

web_search(Hermes内置，DuckDuckGo后端)在物种章鱼研究中0/3超时，被确定为搜索管线最弱层。

## 根因

web_search和ddgs使用同一个DuckDuckGo后端，但实现路径不同：
- ddgs = Python库，直接调API，无中间层 → 9/9全命中
- web_search = Hermes内置，经过Hermes层 → 0/3超时

**问题在Hermes实现层，不在DuckDuckGo本身。**

## 决策

| # | 决策 | 理由 |
|---|------|------|
| D1 | ddgs升Tier 0.5+（主力搜索引擎） | 实测9/9全命中（英/中/学术），与Tier 0（arXiv API）和Tier 0.5（本地缓存）并列 |
| D2 | web_search降Tier 2（后备） | 实测0/3超时，不可靠。仅在ddgs不可用时使用 |
| D3 | 补强最弱层=换实现非修实现 | 同一后端不同路径=不同结果。内置工具≠最优工具 |

## Tier新结构（v2.3.2）

```
Tier 0:    结构化API (arXiv/HN/GitHub/Reddit/Pubmed)  ← 最可靠
Tier 0.5:  本地知识库 (wiki/jiak/RECALL)              ← 零网络依赖
Tier 0.5+: ddgs Python库 (from ddgs import DDGS)       ← 实测100%命中
Tier 1.5:  cnscrape MCP (知乎/B站/微博/头条)           ← 中文社区最可靠
Tier 2:    web_search (Hermes内置)                     ← 不稳定，仅后备
Tier 3.5:  bing_search                                ← 已死
Tier 4:    web_fetch.py (curl_cffi)                   ← 最不可靠
```

## 证据

| 查询类型 | ddgs | web_search |
|----------|:----:|:----------:|
| 英文 | ✅ 3/3 | ❌ 超时 |
| 中文 | ✅ 3/3 | ❌ 超时 |
| 学术 | ✅ 3/3 | ❌ 超时 |
| **总计** | **100%** | **0%** |

## 类似先例

| 先例 | 模式 | 状态 |
|------|------|------|
| web_extract(Firecrawl) → web_fetch.py(curl_cffi) | 内置不可靠→独立库替代 | ✅ 已验证 |
| web_search → ddgs | 内置不可靠→独立库替代 | ✅ 本次验证 |

## 产出物

- search-pipeline skill v2.3.2
- jiak卡片：fata-gates, context-meta-application, jika-engine
- lesson备忘录：tentacles/lesson/
- MEMORY更新
