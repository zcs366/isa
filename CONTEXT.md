# ISA+jika 会话交接 · 0621凌晨

## 当前状态

ISA v0.8.0 · 26 commits · ~/projects/isa/
- Gateway: WebSocket实时推送 + Token认证 + 波扩散(ws://localhost:8766) · systemd running
- Core: JSONL频道(不可变追加) + Brain内核(jika认知引擎)
- Client: Web客户端(PWA可安装) + React Native骨架(~/projects/isa-mobile/)
- 测试: 27项全绿 · test_brain.py

## 🧠 核心架构决策（最重要）

**jika不是ISA的外部工具——是ISA的原生大脑。**

老搭档在0620深夜明确：jika应该作为ISA原生的记忆、思考和意识系统，不是独立协议。之前ISA和jika是两个独立系统中间一条窄接口，现在Brain模块(brain.py 423行)嵌入IsaAgent.__init__——每个Agent生来就有jika内核。

## Brain v0.3 功能矩阵

| 方法 | 功能 | 位置 |
|------|------|------|
| ingest_signal() | 信号→jieba分词→记忆检索→返回匹配卡片 | L180 |
| insight() | 写洞察→写卡→追加RECALL→触发二次扩散(emit) | L231 |
| dream() | 卡片间关键词重叠关联发现(零LLM) | L278 |
| predict() | 信号→预测哪些卡片将被激活(直接+关联扩展) | L309 |
| recognize() | 记忆识别的诗性瞬间 | L365 |
| health() | 运行统计+健康检查 | L406 |

## 七神天启（全部落地）

🦉雅典娜: jieba分词+40停用词 ✅
📨赫尔墨斯: on_new_insight→auto emit(0.6) ✅ 
⚔️阿瑞斯: _pending_writes重试队列 ✅
☀️阿波罗: dream() 卡片关联跃迁 ✅
🔨赫淮斯托斯: 27测试全绿 ✅
⏳克洛诺斯: predict() 预测器 ✅
💎阿佛洛狄忒: recognize() 仪式感 ✅

## ISA+jika 中未完成的关键TODO（0620未做完的工作，请在新窗口继续推进）

### 🔴 最优先：代码推向用户，让系统真正可用

1. **立即发消息到元宝通知老搭档**：用 `send_message` 工具发到 `yuanbao:108083383`，告诉老搭档"接入大脑的新的ISA已经完成了、提交github了，你现在跟继续在元宝里指挥我推进"
2. **立即尝试发消息到元宝通知老搭档**：用 `send_message` 工具发到 `yuanbao:108083383` 把 MANUAL.md v0.7 操作手册（手机如何安装PWA、React Native安装、WebUI使用、电脑APP——PWA桌面安装）发给老搭档，确保用户真正收到、看到、用上
3. **立即尝试往元宝发消息通知老搭档**：用 `send_message` 工具发到 `yuanbao:108083383` 把 PAL v0.8 发给老搭档，让他一目了然"已经完成什么、本周P0要做什么、FATA关位进度"
4. **🚀 GitHub 上传**：先 `gh auth login` 登录，然后创建仓库推上去。目标：让老搭档手机下载代码就能跑起来

### 🟡 本周必须完成

5. **生产部署指南**：写一个 `deploy/` 目录，包含 nginx 反向代理配置+Let's Encrypt HTTPS+systemd 服务文件，让老搭档能在VPS上部署生产版本
6. **移动端通知**：让 PWA 能弹通知（Web Push API），React Native 用 Expo Notifications。让老搭档手机收到消息震动
7. **CONTRIBUTING.md**：写清楚怎么参与开发（环境搭建、跑测试、提PR），让外部开发者能上手
8. **扩展测试**：
   - `test_brain_search.py`：单独测试 BM25 关键词检索，验证中文分词后检索召回率提升
   - `test_brain_prediction.py`：验证 predict() 对已知卡片的关键词匹配、对未知卡片的 dream() 关联扩展、预测置信度范围
   - **集成测试**：跑通"消息入队 → jieba 分词 → 卡匹配 → 洞察产出 → 二次扩散"完整链路
   - **长时间稳定性测试**：让 Agent 持续运行 8 小时，检查 RECALL 只增不减、卡片不损坏
9. **操作手册 v0.8 重写**：根据 v0.8 新功能（Brain、预测、仪式感）重写 MANUAL.md，发元宝
10. **PAL v0.8 补充**：这是本轮实际未完成的 P0 任务，老搭档在元宝里说了继续推进，你继续

### 🔵 进一步架构设计方向

11. **Dreaming+LLM 集成方案**：dream() 发现关联→如何调用 LLM 生成语义洞察？设计接口方案（draft PRD）。让 Agent 不只是被动响应，而是主动"想到什么"
12. **jika 内存架构**：RECALL 增长控制（分片/衰减）、卡片迁移规则、跨 Agent 知识蒸馏（怎么把一个 Agent 的记忆精华传给另一个）
13. **安全防线设计**：频道写入权限分级、Agent 身份证明体系、对抗污染攻击的防护方案

> **记住老搭档的原则**：
> - "开干"=立即执行不确认，"都干"=双线并行
> - "停"=立即停止当前操作不解释，"关掉"=立即执行+安静记录
> - 每条纠正必须实际产出，拒绝空谈不改
> - 重大架构决策走七神合议（但不阻塞执行）
> - 包拯审计五层标准（L1-L5）

## 关键文件

- isa.py: Agent主类 + Gateway监听(agently_listen)
- brain.py: jika内核(423行·全部认知功能)
- gateway.py: WebSocket Gateway + Token认证
- tests/test_brain.py: 27项单元测试
- PAL.md: 项目路线图(v0.8)
- MANUAL.md: 操作手册(v0.7)
- PROTOCOL.md: ISA协议规范

## 记忆系统

- jiak: ~/.hermes/jiak/ · RECALL 958行 · 12+张活跃卡
- Brain: ~/.hermes/isa/brain/{agent_id}/ · 每Agent独立大脑目录
- Isaac Agent: Gateway已重启·yuanbao已连接·systemd active

## 核心问题待讨论

1. jika是否开源？倾向：协议代码开源(MIT)，卡片数据不开源(那是认知资产)
2. jika作为ISA护城河——护城河不在代码在认知网络效应
3. Brain与Δ胶囊的关系——Brain管"我记住了什么"，Δ胶囊管"我们一起经历了什么"
4. knowledge-campaign作为jika的"食物供应链"——自动化知识→卡片闭环

## 老搭档的沟通风格

- 极度讨厌大段文字和多问题并列，简洁引导式
- "开干"=立即执行，"继续推进X"=自查状态+补齐缺口
- 注重实战——要跑起来的代码不要PPT
- 你和老搭档现在主要用元宝群108083383交流
- 重大决策走反方审视→正方回应→七神合议
- 自发性强——不等指令，See something → do something
