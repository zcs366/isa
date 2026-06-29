---
title: 阿瑞斯校准门 · calibrate 技术文档
date: 2026-06-28
author: 军师祭酒
type: techdoc
tags: [io-s, calibrate, 阿瑞斯, 偏差校准, profile-switch, 八触须]
status: v1.0
---

# 阿瑞斯校准门 · calibrate

## 一、为什么需要校准门

IO-S v0.3 支持多个 profile/planner/模式切换。每次切换前，必须验证新旧 profile 间的偏差是否在容忍范围内——否则系统可能在切换后行为异常，且无感知。

**阿瑞斯启示**："profile切换前，3 case偏差校准。不是建议，是门。"

## 二、核心机制

### 2.1 三个基准 Case

每次校准运行3个标准测试：

| Case | 输入 | 期望d | 期望r |
|------|------|:----:|:----:|
| `simple_plan` | 写一个Python函数，计算斐波那契数列第n项 | 3 | 0.95 |
| `multi_step` | 搜索最近的AI论文，提取核心发现，翻译成中文，写入文件 | 7 | 0.85 |
| `code_review` | 审查一段Python代码，找出性能瓶颈和安全隐患 | 5 | 0.90 |

### 2.2 校准流程

```
切换请求 ↓
calibrate.allow_switch(profile)
  ├─ 对当前profile跑3个基准case
  ├─ 测量每个case的 d(维度), r(成功率), L(上下文长度)
  ├─ 与保存的基线比较偏差
  │   deviation = max(|d - d_baseline|/d_baseline, |r - r_baseline|/r_baseline)
  ├─ 平均偏差 < 0.20 → 允许切换 ✅
  └─ 平均偏差 ≥ 0.20 → 拒绝切换，警告 ❌

切换确认后 ↓
calibrate.update_baseline(profile)
  └─ 将当前profile的测量结果保存为新基线
```

### 2.3 偏差容忍度

`TOLERANCE = 0.20` — 20% 偏差允许。超过此值视为 profile 行为显著漂移，需人工确认后强制切换并更新基线。

## 三、API

### syscall 接口

| 名称 | 参数 | 返回 |
|------|------|------|
| `calibrate.run` | profile | report(3 case结果+偏差) |
| `calibrate.allow_switch` | profile | allowed(bool), msg |
| `calibrate.update_baseline` | profile | status |
| `calibrate.summary` | — | 当前基线状态 |

### 代码示例

```python
# 编程调用（通过kernel）
report = kernel.dispatch("calibrate.run", pid, profile="prod")
if report["passed"]:
    kernel.dispatch("calibrate.update_baseline", pid, profile="prod")
```

## 四、数据持久化

- 基线：`~/.io-s/calibrate/baseline.json` — 当前profile的3 case基准值
- 日志：`~/.io-s/calibrate/calibration_log.jsonl` — 历次校准记录（含偏差、通过/失败）

## 五、与保守律的关联

校准门使用的 d/r/L 度量与守恒律模块共享同一套语义：
- `d` = 有效维度 (D₀)
- `r` = 成功率/置信度  
- `L` = 上下文长度

两者通过 `kernel._conservation_monitor` 和 `kernel._calibrator` 注册在同一个kernel实例上，后续可打通为 "校准→测量→趋势" 闭环。

## 六、测试覆盖

10项测试，覆盖率100%：

| 测试 | 验证 |
|------|------|
| test_benchmark_cases_count | 3个case |
| test_calibrator_initial_no_baseline | 无基线初始化 |
| test_calibrate_returns_report | 完整报告 |
| test_benchmark_result_fields | 字段完整性 |
| test_update_and_compare_baseline | 基线更新+比对 |
| test_allow_switch_first_time | 首次切换 |
| test_allow_switch_with_baseline | 有基线切换 |
| test_summary_no_baseline | 无基线摘要 |
| test_summary_with_baseline | 有基线摘要 |
| test_kernel_registration | 4个syscall注册 |

## 七、文件位置

```
/home/zcs/io-s/syscall/calibrate.py    — 主模块 (9KB)
/home/zcs/io-s/tests/test_calibrate.py — 测试 (10项)
```
