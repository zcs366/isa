# ISN-IO-S接口静默拒绝 — 最危险的失败模式

> 签发人：军师 · 日期：2026-06-27 · 关键词：ISN, IO-S, 静默拒绝, cap_denied, SYSCALL_RESOURCE_MAP, 踩坑

## 一、问题

ISN通过signal_send()向IO-S发送信号，但IO-S无声吃掉所有信号——ISN完全不知道自己的信号被拒绝了。

**这是治理系统最危险的失败模式：静默拒绝。** 比报错更危险——报错你知道出了问题，静默拒绝你以为一切正常。

## 二、根因分析

### 2.1 调用链

```
ISN signal_send(envelope) 
  → kernel.py dispatch() L219
  → 读取resource和operation字段
  → ISN的args只含{signal:envelope}，缺resource和operation
  → dispatch()读到空串""
  → cap.check(isn, "", "")
  → resource type ""不存在
  → 返回cap_denied
  → 无日志、无异常、无反馈
```

### 2.2 为什么发现这么晚

1. ISN调用signal_send后没有检查返回值
2. IO-S的cap_denied没有抛异常，只返回枚举值
3. 两端都假设对方会处理错误——典型的"责任真空"
4. 没有集成测试覆盖ISN→IO-S路径

## 三、修复方案

```python
# kernel.py 新增
SYSCALL_RESOURCE_MAP = {
    "signal_send": ("signal", "send"),
    "signal_recv": ("signal", "recv"),
    "skill_register": ("skill", "register"),
    # ... 18条映射
}

def dispatch(caller, syscall_name, args):
    if "resource" not in args or "operation" not in args:
        # 自动推断，而非静默失败
        inferred = SYSCALL_RESOURCE_MAP.get(syscall_name)
        if inferred:
            args["resource"] = args.get("resource", inferred[0])
            args["operation"] = args.get("operation", inferred[1])
        else:
            raise ValueError(f"Unknown syscall: {syscall_name}, no resource/operation in args")
    # ... 正常cap检查
```

## 四、教训

### 教训1：静默拒绝 > 报错

在治理系统中，静默拒绝是最危险的失败模式。ISN以为自己在发信号，IO-S以为自己在正常工作——实际上所有信号都被丢弃了。

### 教训2：返回值必须检查

ISN的signal_send调用后没有检查返回值。任何涉及跨系统调用的代码，必须检查返回值或使用异常。

### 教训3：责任真空

"我假设你会处理" = 没人处理。每个接口的错误处理责任必须明确归属于调用方或被调用方，不能"双方都假设对方处理"。

### 教训4：集成测试覆盖关键路径

ISN→IO-S是关键路径，但没有集成测试。单元测试只能验证单个模块，不能验证模块间的信号传递。

## 五、结论

1. 已修复：kernel.py新增SYSCALL_RESOURCE_MAP(18条映射) + dispatch()自动推断逻辑
2. 待验证：ISN实际调用signal_send后的返回值检查
3. 长期：所有跨系统接口必须有集成测试 + 错误处理明确归属

## 六、待办

- [ ] ISN端signal_send调用增加返回值检查
- [ ] IO-S cap_denied时至少写一条日志
- [ ] ISN→IO-S集成测试编写
- [ ] 所有跨系统接口审计：是否存在同类静默拒绝
