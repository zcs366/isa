# output 归藏协议 · 联邦法第2号（修订版）

> **立法者**：军师祭酒 | **颁布**：2026-06-28 | **修订**：2026-06-28 | **执行者**：IKO
> **河床**：产出物=I:/hermes/output/ | 边界=写输标准+归藏约束 | 法体系=L5协议法

---

## 一、Canonical Output 声明

```
主存储（长期归档）：I:/hermes/output/   ← 文档的家
工作区（短期活跃）：~/hermes/output/    ← 当前工作的临时落脚
```

**铁律**：
- 文档的**最终归宿**是 I盘。C盘是工作区，不是家。
- I盘 = 备份 + 分担C盘存储压力
- C盘产出定期归档到 I盘

### 不会迁移的

| 地址 | 角色 | 说明 |
|------|:----:|------|
| `I:/hermes/output/` | **主仓** | 1669篇，不动 |
| `C:/Users/.../hermes/output/` | 旧工作区 | 已迁，原址留标记 |
| `C:/Users/.../hermes-shared/output/` | 旧共享区 | 已迁，原址留标记 |

---

## 二、写输标准（八触须格式）

每个写入 `~/hermes/output/` 的 .md 文件必须包含：

```yaml
---
date: 2026-06-28
author: 军师
project: openLLM
type: memo
---
```

| 必填 | 说明 |
|------|------|
| 文件名 | `YYYY-MM-DD_名称_为啥事.md` |
| 关键词行 | `> 关键词：词1, 词2, 词3` |
| ##章节 | 至少一个 ## 级标题 |
| 结论章节 | `## 结论` / `## 总结` 等 |

**IKO 校验器**：`~/projects/isa/octopus/validate_tentacle.py`  
不合规 → 拒绝归档 → 不进章鱼索引。

---

## 三、SA 输出协议

```
SA 自由创作（任意格式、任意位置）
    ↓
归档到 tentacles/ 时 → IKO 格式化成八触须标准
    ↓
章鱼自动索引 → 任何 Agent 可搜
```

**铁律**：SA 不关心格式，IKO 不关心内容。各守边界。

---

## 四、散落文档收容规则

| 散落位置 | 归入 |
|----------|------|
| Windows 桌面 `IDC-memos/` | `output/IDC/memos/` |
| `~/work/` | `output/work/` |
| `~/wiki/` | `output/wiki/` |
| `~/izu/` | `output/izu/` |
| `~/SOUL.md` | `output/identity/SOUL.md` |
| 下载目录 Hermes 手册 | `output/manuals/` |
| SA 在 /tmp/ 产生的最终交付物 | **必须迁入 output/，/tmp/ 重启即丢** |

---

## 五、归藏审计

| 项 | 内容 |
|----|------|
| 审计者 | 萧何 (xiaohe-output-guardian) |
| 频率 | 每 6h |
| 检查 | 孤儿文件、死链接、命名合规、INDEX 一致性 |
| 违规 | 推 Telegram |

---

## 六、章鱼索引覆盖

`octopus_feed.py` 自动扫描：
- `~/hermes/output/` — 主产出
- `~/hermes/wiki/` — 知识库
- `~/hermes/plans/` — 计划文档
- `~/.hermes/jiak/cards/` — 卡片内容

---

*本法自颁布起生效。IKO 负责执行，包拯负责审计。*
