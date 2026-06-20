# 贡献指南 · ISA

ISA是语义共振通信平台——Agent互联协议。内置jika认知引擎。

## 快速上手

```bash
git clone git@github.com:zcs366/isa.git
cd isa
pip install -e .
python3 -m pytest tests/ -q    # 31 passed
```

依赖：Python >= 3.10 · jieba >= 0.42 · websockets >= 12.0

## 项目结构

```
isa/
├── isa.py              # Agent主类 + Gateway监听 + 波扩散引擎
├── brain.py            # jika认知引擎 (信号→记忆→检索→梦境→预测)
├── gateway.py          # WebSocket Gateway + Token认证
├── hermes_adapter.py   # Hermes Agent桥接
├── client/             # Web客户端 (PWA可安装)
│   ├── index.html      # 716行单页应用
│   ├── manifest.json   # PWA配置
│   └── sw.js           # Service Worker离线缓存
├── tests/
│   └── test_brain.py   # 31项单元测试
├── PAL.md              # 项目路线图
├── CONTEXT.md          # 架构决策背景
├── MANUAL.md           # 操作手册
└── PROTOCOL.md         # ISA协议规范
```

## 架构

四层：Client(PWA/Web) ↔ Gateway(WebSocket+Token) ↔ Core(JSONL频道+Brain内核) ↔ Brain(jika卡片+检索+梦境)

每个ISA Agent启动时自动初始化Brain——拥有持久记忆和自主Dreaming能力。

## 开发

```bash
# 跑测试
python3 -m pytest tests/ -v

# 启动Gateway
python3 gateway.py --host 0.0.0.0 --port 8766

# 启动Agent (自动开始Dreaming)
python3 isa.py --id 军师 --agently-listen

# 启用LLM增强梦境
ISA_DREAM_LLM=http://localhost:11434/v1 python3 isa.py --id 军师 --agently-listen
```

## 提交规范

- 每个commit一个主题
- 测试必须通过 (`pytest tests/`)
- 新功能带测试
- commit message格式: `🧠 功能: 简短描述`

## 方向锚

PAL.md 定义了当前路线图。重大方向变更需讨论。
核心决策权保留在项目维护者。

## 许可

MIT License
