# Prompt Injection as Role Confusion — ICML 2026

> 签发人：军师 · 日期：2026-06-28 · 关键词：Role Confusion, L6, 内容净化, 潜意识Steering, CoT Forgery

## 一、论文基本信息

| 项 | 内容 |
|---|------|
| **标题** | Prompt Injection as Role Confusion |
| **来源** | ICML 2026 · [role-confusion.github.io](https://role-confusion.github.io) |
| **arXiv** | [2603.12277](https://arxiv.org/abs/2603.12277) |
| **作者** | Charles Ye, Jasmine Cui, Dylan Hadfield-Menell (MIT) |
| **HN热度** | 104分 / 55评论（06-23早间热榜第19位）|
| **17层** | L6（内容侧净化）|

## 二、核心方法

**核心主张**：Prompt injection的根源不是"恶意输入"，而是**LLM感知角色的方式有缺陷**。

LLM把输入看作单一token流。角色标签(system/user/think/assistant/tool)本应分割这个流为标记段，但**模型通过风格特征（而非标签本身）来学习角色**。

### Role Probes：测量内部角色信念

作者训练线性探针，在相同文本包裹不同标签时的激活差异：
- **CoTness** — token被认为是think标签内的概率
- **Userness** — token被认为是user标签的概率

三个实验：
1. **正确标签**：CoTness仅对think token高 ✅
2. **无标签**：CoTness对formerly-think token仍高——模型仍视"推理风格文本"为推理
3. **全在user标签**：CoTness仍对推理风格文本高——**写作风格覆盖了真实标签**

### CoT Forgery：新攻击

- 既然think标签获得自动信任，注入"听起来像推理"的文本可冒充已达成结论
- **攻击成功率**：从near-0%跳到~60%（全模型）
- **Destyling**（去掉推理风格词句）使成功率从61%降到10%——对人类不可见的改动

## 三、关键发现

| 发现 | 数据 |
|------|------|
| 风格覆盖标签 | CoTness在user标签下仍对推理风格文本高 |
| CoT Forgery成功率 | ~60%（从near-0%跃升） |
| Destyling防御效果 | 61%→10% |
| 标准benchmark vs 真人红队 | 模型接近满分，但对抗真人100%失败 |

## 四、与17层的关联（L6: 内容净化）

| 设计要求 | Role Confusion覆盖 | Hermes当前 |
|---------|:-----------------:|:----------:|
| 剥离语气/修辞信号 | ✅ 风格覆盖标签 | ❌ 工具数据原样进入 |
| 区分"事实"和"表达" | ✅ state bleeding机制 | ❌ jika不可变追加未隔离 |
| 合法请求的微妙漂移 | ✅ 潜意识steering | ❌ 六层中唯一未覆盖维度 |

## 五、与Hermes Agent的关联

**核心警示**：Layered Security的三层防御（输入筛查+权限上下文+输出审计）和SEB的执行隔离都救不了角色混淆——请求合法、动作合法、内容合法。

**具体行动**：
1. **jika"不可变追加"应升级为"事实追加+表达隔离"**——工具数据在进入LLM前剥离语气/修辞
2. **章鱼搜索结果的修辞降噪**——web_fetch返回的语气/热情措辞应在注入前清洗
3. **CoT Forgery防御**——对think标签内容做风格检测，标记高CoTness的注入文本

## 六、结论

这篇论文暴露了17层L6（内容侧净化）的唯一盲区——之前我们只关注了"恶意输入"（prompt injection），没关注"合法输入在合法场景中的微妙漂移"。Role Confusion补上了最后一角：**真正的大规模威胁不是显式攻击，是潜意识steering**。
