# 踩坑记录：web_search+bing全线崩溃与搜索管线韧性

> 日期：2026-06-28 · 类型：lesson · 关键词：web_search故障, bing失效, 搜索韧性, ISN改进, 通道健康检查

---

## 踩坑描述

物种章鱼研究执行过程中，web_search(DuckDuckGo/Yahoo/Brave后端)返回连续超时错误，bing_search返回0结果。两个Tier 1级搜索引擎同时崩溃，导致6/9搜索通道不可用。

## 根因

- **web_search**：DuckDuckGo/Yahoo/Brave后端不可达（原因不明，非代理问题——cnscrape MCP正常）
- **bing_search**：Cloudflare Turnstile CAPTCHA拦截（2026-06-24已确认）

## 影响

- 搜索范围受限（33%通道不可用）
- 被迫降级到arXiv API（Tier 0）和cnscrape MCP（Tier 2）
- 发现arXiv对生物学论文覆盖偏CS的新pitfall

## 教训

| # | 教训 | 来源 |
|---|------|------|
| 1 | **容错设计的价值在崩溃时才显现** | Tier 0（arXiv API）和Tier 2（cnscrape）在Tier 1崩溃时仍正常工作——分层架构有效 |
| 2 | **单一场景验证不够** | web_search在古代周报中5/5命中，在章鱼研究中0/3超时——质量信号必须跨场景积累 |
| 3 | **搜索管线的可靠性=最弱层** | Tier 1（web_search）是最弱层——它崩溃时用户体验断裂，即使Tier 0仍正常 |
| 4 | **通道健康检查=强制前置步骤** | 搜之前验证各Tier在线，不等失败再降级。+30s避免分钟级无效搜索 |
| 5 | **cnscrape MCP比web_search更稳定** | 实证：两个场景中cnscrape都正常——Tier 2应升Tier 1.5 |

## 最佳实践

1. **搜之前先做通道健康检查**（search-pipeline v2.3.1新增）
2. **Tier分级必须基于多场景实证**，非单一场景验证
3. **搜索失败是正面信号**——暴露管线弱点，触发ISN改进
4. **降级不等于失败**——arXiv API+cnscrape在web_search崩溃时仍能工作

## 关联

- search-pipeline skill v2.3.1（ISN改进）
- jiak卡片：fata-gates, jika-engine, izu-research-pipeline
- 决策记录：tentacles/decision/2026-06-28_decision_搜索管线Tier重评与通道健康检查.md
