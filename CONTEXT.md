# ISA+jika 新会话启动Prompt · 0621凌晨

## 当前状态

ISA v0.8 · 30 commits · GitHub: https://github.com/zcs366/isa
- Gateway: WebSocket + Token认证 + 波扩散 · systemd running
- Core: JSONL频道(不可变追加) + Brain内核(jika认知引擎 v0.3)
- Client: PWA可安装 + React Native骨架(~/projects/isa-mobile/)
- 测试: 31项全绿 · test_brain.py
- 文档: MANUAL v0.8 · CONTRIBUTING.md · PAL v0.8 · PROTOCOL.md

## 核心架构：ISA·jika·Δ胶囊三角

ISA是管道，jika是大脑，Δ胶囊是硬盘。三者独立进化，接口对齐。

| 组件 | 职责 | 状态 |
|------|------|------|
| ISA | Agent间通信(WebSocket+JSONL+波扩散) | ✅ v0.8·30 commits |
| jika/Brain | 单Agent认知(卡片+检索+梦境+预测+仪式感) | ✅ v0.3·530行·31测试 |
| Δ胶囊 | 群体共享状态(梅克尔链+BGE-zh+SQLite) | 🔨 v0.2·brain_dream桥已建 |

## Brain v0.3 功能矩阵

ingest_signal() — 信号→jieba分词→记忆检索
insight() — 写洞察→写卡→RECALL→二次扩散(emit)
dream() — 卡片间关键词重叠关联发现
predict() — 预测信号将激活哪些卡片
recognize() — 记忆识别的诗性短语
start_dreaming(interval, llm_endpoint) — 后台线程·定时扫描→调LLM→洞察
_llm_dream() — OpenAI兼容协议·15s超时·降级
_log_dream_event() — 写入brain_dream.jsonl供Δ胶囊消费

## Dreaming引擎

Agent连接Gateway后自动启动（5分钟扫描间隔）。
无LLM：纯关键词关联。有LLM：设ISA_DREAM_LLM=http://localhost:11434/v1。

## P0待办

- Δ胶囊消费brain_dream.jsonl管线（三角最薄弱环节）
- 移动端通知(PWA Push API)
- 生产部署指南(nginx+wss+systemd)
- 扩散免疫v1

## 关键文件

isa.py · brain.py(530行) · gateway.py · tests/test_brain.py · CONTEXT.md · PAL.md

## 记忆系统

jiak: ~/.hermes/jiak/ · RECALL ~1030行
Brain: ~/.hermes/isa/brain/{agent_id}/

## 老搭档风格

"开干"=立即执行·"继续推进X"=自查+补缺口·不等指令
