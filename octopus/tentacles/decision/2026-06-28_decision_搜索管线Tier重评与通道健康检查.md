# 决策记录：搜索管线Tier重评与通道健康检查协议

> 日期：2026-06-28 · 类型：decision · 关键词：搜索管线, Tier分级, 通道健康检查, ISN改进

---

## 背景

物种章鱼重锚研究中，web_search(DuckDuckGo/Yahoo/Brave)全线超时+bing_search返回0结果。6/9搜索通道有效，但Tier 1(web_search)同时崩溃导致用户体验断裂。

## 决策

| # | 决策 | 理由 |
|---|------|------|
| D1 | cnscrape MCP从Tier 2升Tier 1.5 | 实证：在web_search崩溃场景中cnscrape仍正常（知乎/B站搜索命中），是最可靠的Tier 0-1桥梁 |
| D2 | web_search标注"不稳定" | 实证：古代周报5/5命中 vs 章鱼研究0/3超时——跨场景表现差异极大，不可标注为"可靠" |
| D3 | 通道健康检查成为强制前置步骤 | 工程原则：搜之前验证各Tier在线，不等失败再降级。+30s启动时间避免分钟级无效搜索 |
| D4 | bing_search维持Tier 3.5（已死） | 2026-06-24至2026-06-28连续三次实测确认：词典页/无关结果/0结果 |

## Tier新结构（v2.3.1）

```
Tier 0:   结构化API (arXiv/HN/GitHub/Reddit/Pubmed)     ← 最可靠
Tier 0.5: 本地知识库 (wiki/本地缓存/jiak/RECALL)          ← 零网络依赖
Tier 1:   ddgs (DuckDuckGo)                               ← 通用搜索
Tier 1.5: cnscrape MCP (知乎/B站/微博/头条)               ← 中文社区最可靠
Tier 3.5: bing_search                                     ← 已死
Tier 4:   web_fetch.py (curl_cffi)                        ← 最不可靠
```

## 证据

| 场景 | web_search | bing_search | arXiv API | cnscrape |
|------|:----------:|:-----------:|:---------:|:--------:|
| 古代学术周报(2026-06-28 cron) | ✅ 5/5 | ❌ 0/5 | — | — |
| 物种章鱼研究(2026-06-28) | ❌ 超时 | ❌ 0结果 | ✅ | ✅ |
| 物种章鱼重锚版(2026-06-28) | ❌ 超时 | ❌ 0结果 | ✅ | ✅ |

## 产出物

- search-pipeline skill v2.3.1（ISN改进）
- jiak卡片：fata-gates, jika-engine, izu-research-pipeline
- MEMORY：搜神纪律条目
- lesson备忘录：tentacles/decision/
