# SA生命周期Plugin执行报告 — Plugin落地与端到端验证

> 作战单位：子贡(编码) + 鲁班(架构) + 韩信(合议) + 军师(决策) · 日期：2026-06-27 · 关键词：SA生命周期, Plugin, 端到端验证, semantic_field, hello/goodbye

## 一、任务概述

实现SA（Software Agent）生命周期管理——话起即生话毕即死。核心机制：session启动时自动注册语义场（hello），结束时自动注销（goodbye），每轮对话刷新心跳TTL。

## 二、产出物清单

| 产出 | 路径 | 说明 |
|------|------|------|
| SALifecycle包装类 | `~/.hermes/plugins/sa_lifecycle/` | Plugin主体 |
| 三钩子 | `on_session_start/on_session_finalize/pre_llm_call` | 生命期管理 |
| TTL心跳 | pre_llm_call刷新TTL | 防误下线 |
| Semantic Field | 共享文件系统 | 窗口注册表 |

## 三、关键里程碑

### 钩子触发时序
```
session启动 → on_session_start(write hello + register semantic_field)
  → pre_llm_call(刷新TTL + wink心跳) [每轮]
  → session结束 → on_session_finalize(write goodbye + unregister semantic_field)
```

### 端到端验证（2026-06-27 00:10~00:35）
1. ❌ 首次失败：Hermes自动加载失败（Plugin需显式`hermes plugins enable`）
2. ✅ 第二次：手动启用后正常
3. ✅ E2E通过：两新窗口自动注册语义场，话起即生验证通过

## 四、测试结果

| 阶段 | 状态 | 说明 |
|------|------|------|
| 手动测试 | ✅ | 单窗口注册/注销正常 |
| 自动加载 | ❌→✅ | `plugins enable`显式启用 |
| 新建窗口 | ✅ | 两个新窗口自动注册 |
| TTL超时断开 | ✅ | 超时后正确unregister |

## 五、发现的问题与隐患

### 已修复
1. TTL 120s → 600s（第二窗口因TTL过期断开）
2. Plugin自动加载 + `plugins enable` 显式启用

### 待修复（五大隐患）
1. **路径硬编码**：Plugin中硬编码`/home/zcs/`路径
2. **JSON并发**：共享文件同时写入无锁
3. **TTL无心跳**：pre_llm_call未刷新TTL（P0已修复）
4. **SIGKILL不goodbye**：进程被杀死无法触发注销
5. **与federal_boot双系统**：sa_lifecycle与federal_boot并行，交互未验证

## 六、下一步

- [ ] 五大隐患修复（P0: 路径硬编码 + 心跳刷新已完）
- [ ] 集成Hermes session（非Plugin自管理）
- [ ] federal_boot + sa_lifecycle双系统整合测试
