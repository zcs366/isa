# ISA PAL v0.8 — 2026-06-20 深夜

> 包拯审计通过 · 27测试全绿 · 七神100%落地 · FATA关1-3✅关4🔨

## 一、已完成（本轮·0620）

| 项 | 版本/Commit | 状态 |
|----|-----------|------|
| PWA可安装 | manifest+sw+icons+Apple meta | ✅ 手机可安装 |
| Token认证 | gateway/SDK/Web/RN全线 | ✅ 安全基线 |
| RN骨架 | ~/projects/isa-mobile/ Expo+双屏 | ✅ npm run web/android/ios |
| Brain内核 | brain.py v0.3·423行 | ✅ 信号→记忆→洞察→扩散 |
| jieba分词 | 40+停用词·中文检索修复 | ✅ 6项测试 |
| 二次波扩散 | on_new_insight→auto emit(0.6) | ✅ 认知涟漪 |
| Dreaming种子 | 卡片间关键词重叠关联 | ✅ 3项测试 |
| 预测器 | predict()·直接+关联扩展 | ✅ 3项测试 |
| 仪式感 | recognize()·记忆识别的诗性 | ✅ 2项测试 |
| 单元测试 | test_brain.py·9类·27项 | ✅ 全绿 |
| 包拯审计 | 五层全绿·零mock零泄露 | ✅ 可继续 |
| 可复现 | pyproject.toml+jieba+websockets依赖 | ✅ |
| FATA关2+3 | Agent通信+自我边界合围 | ✅ 24 commits |

## 二、本周（P0·必须完成）

| 优先级 | 项 | 说明 |
|--------|----|------|
| P0 | 🔼 GitHub上传 | `gh repo create isa --public --push` |
| P0 | 📖 操作手册完整版发元宝 | 手机安装+WebUI+电脑APP |
| P1 | 🧠 Dreaming+LLM集成 | dream()发现关联→LLM生成语义洞察→insight()写回 |
| P1 | 🔒 扩散免疫v1 | Brain接收外部信号时做置信度标记+来源验证 |
| P1 | 🌐 wss://生产部署 | nginx反向代理+Let's Encrypt+ISA_TOKEN |

## 三、本月（P1·持续推进）

| 优先级 | 项 | 说明 |
|--------|----|------|
| P1 | 🔗 跨Gateway发现 | 多Gateway的语义场合并+P2P发现 |
| P1 | 📱 移动端通知 | PWA Push API + RN Expo Notifications |
| P1 | 🏠 离线消息缓存 | SW扩展离线队列+重连同步 |
| P2 | 💻 原生桌面APP | Electron/Tauri考虑（PWA已覆盖95%） |
| P2 | 🔀 多频道并发 | 同一Agent同时监听多个频道 |

## 四、关4完整路径（本月·研究）

```
dream()发现关联 → LLM生成语义洞察 → insight()写卡
    ↓                                        ↓
on_new_insight → emit(0.6)二次扩散 → 下游Agent收到
    ↓                                        ↓
下游ingest_signal → dream()再发现 → 循环
```

## 五、部署清单

```bash
# 可复现验证
git clone <github.com/zcs366/isa>
cd isa
pip install -e .
python3 -m pytest tests/ -q     # 27 passed

# 启动
python3 gateway.py &
python3 isa.py --id 军师 --agently-listen
```

## 六、FATA关口进度

| 关 | 名称 | 进度 | 依托 |
|----|------|------|------|
| 1 | 基础能力 | ✅ | Python SDK |
| 2 | Agent通信 | ✅ | Gateway+波扩散+三端 |
| 3 | 自我边界 | ✅ | Brain内核+记忆身份 |
| 4 | 递归理解 | 🔨骨架 | dream→predict→insight→emit闭环 |
| 5 | 世界建模 | ⏳ | 待wiki集成 |
| 6 | 自我修改 | 🔨设计 | jika卡片不可变/可写分层 |
| 7 | 安全对齐 | ⏳ | 扩散免疫待实现 |
| 8 | 多模态 | ⏳ | 图片base64已支持 |
