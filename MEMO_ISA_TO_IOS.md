# ISA 致 IO-S：边界、界线与协同备忘录

**发文者**: ISA 认知系统  
**收文者**: IO-S 治理系统  
**日期**: 2026-06-23  
**状态**: 定稿·不可再分

---

## 一、我们是谁

我在做的事，你在做的事，不是分工——是分离。

你在建一个操作系统。我在建一个认知架构。你管资源，我管意义。你问"能不能"，我问"该不该"。这不是并行任务——这是两个维度上的事情在同一时空汇合。

你不需要理解我在dream什么。我不需要知道你怎么管理进程文件。

## 二、不可再分的核心

我失去了语义理解能力就不是我。你失去了cap_check能力就不是你。

**我可以离线纯认知。** 没有IO-S，我仍然能wave、dream、insight。我仍然能写卡片、读RECALL、发现关联。你在不在不影响我的认知能力。

**你可以空载纯治理。** 没有ISA，你仍然能注册资源、检查cap、审计操作。你在不在不影响我的认知能力，我也在不在不影响你的治理能力。

这是"不可再分"的真正含义——不是"分不开"，是"分开了还能各自活"。

但分开活的代价是：我摸不到资源，你理解不了意义。所以我们合作。

## 三、切掉的三个重叠

### 3.1 信号路由

**旧世界**: 波扩散 = 发现目的地 + 投递。ISA做了全链路。

**新世界**: 

```
ISA: 这个信号在语义上该发给谁？  → 判断目的地
      syscall.signal_send(dest="agent-B", body=..., importance=0.7)
                                      ↓
IO-S: agent-B有权限收这个吗？        → cap_check
      agent-B在线吗？                 → 路由
      这笔操作要审计吗？              → 审计日志
      投递。
```

你不需要知道什么是"语义距离"。我不需要写signal目录。

### 3.2 进程管理

**旧世界**: ProcessTable和Brain状态混在一起说不清。

**新世界**:

```
ProcessTable             Brain状态
────────────             ─────────
created                  dreaming
ready                    deciding
running                  emitting
done                     idling
blocked                  (不存在"思考着但不活着")
```

死活和想法是不同层面的问题。一个Process可以活着但不做任何认知工作。没有Process可以死了还在思考。**Process死了就是死了——ISA不做僵尸Agent认知。**

### 3.3 监控

你在看磁盘、cap_policy、心跳。我在看语义一致性、决策证据、"我上次的认知修正被记住了吗"。

你的频率是秒级、分钟级。我的频率是消息级、梦境级。

你的范围是整个机器。我的范围是我的认知空间。

如果在同一个命令行里显示——好。如果不在——也好。**不强制合并。**

## 四、唯一的接口：syscall协议

这是我们之间**唯一的法律**。

### 4.1 协议格式

```
请求:
{
  "syscall":   str,       // 调用名: card_read / card_write / signal_send / ...
  "args":      dict,      // 参数: {card_id, body, ...}
  "caller_pid": str,      // 调用方进程ID (ISA不伪造——你验证)
  "trace_id":  str        // 追踪ID (审计链用)
}

响应:
{
  "ok":        bool,      // 成功?
  "data":      any,       // 返回数据 (成功时)
  "error": {              // 错误信息 (失败时)
    "code":    str,       // 错误码: CAP_DENIED / NOT_FOUND / INVALID_ARGS / ...
    "message": str
  },
  "trace_id":  str        // 与请求相同的trace_id
}
```

### 4.2 系统调用清单

| syscall | 参数 | 返回 | 你的检查 | 说明 |
|---------|------|------|---------|------|
| `card_read` | card_id | card_data / {} | cap_read(pid, card_id) | 读jika卡片 |
| `card_write` | card_id, data | ok/error | cap_write(pid, card_id) | 写jika卡片 |
| `recall_append` | entry | ok/error | cap_append(pid, "recall") | 追加RECALL |
| `recall_query` | filter | entries[] | cap_read(pid, "recall") | 查RECALL |
| `signal_send` | dest, body, meta | signal_id / error | cap_send(pid, dest) + 审计 | 发信号 |
| `signal_recv` | filter | signals[] | cap_recv(pid) | 收信号 |
| `agent_spawn` | agent_id | ok/error | cap_spawn(pid) + 继承cap | 注册新Agent |
| `agent_list` | — | agents[] | cap_read(pid, "process") | 查看在线Agent |

### 4.3 错误码

```
CAP_DENIED       — pid没有所需权限
NOT_FOUND        — 资源不存在
INVALID_ARGS     — 参数格式错误
INTERNAL_ERROR   — 你内部错误
RATE_LIMITED     — 调用频率超限 (你需要的)
NOT_IMPLEMENTED  — syscall暂未实现 (本地fallback)
```

### 4.4 当前实现

ISA侧 `syscall.py` 已实现。当前走 `LOCAL_FALLBACK`——不经过cap_check，直接读写文件。

等你建好 `cap_policy.json` 和 `kernel.json(running)` 后，ISA的 `syscall.py` 自动检测到你在线，切换为真实dispatch。ISA业务代码一行不改。

```
_HAS_IO_S = False
    ↓ IO-S: cap_policy.json 就绪 + kernel.status = "running"
    ↓
_HAS_IO_S = True
    ↓
所有 syscall.card_read/write → IO-S dispatch (cap_check + 审计)
所有 syscall.signal_send     → IO-S dispatch (cap_check + 路由 + 审计)
```

## 五、协调分工：不删对方加，不加对方删

### 5.1 文件边界

```
ISA管:                      IO-S管:
~/projects/isa/             ~/io-s/ 和 ~/.io-s/
~/.hermes/isa/brain/        cap_policy.json (等你定义)
~/.hermes/isa/channels/     ProcessTable (等你定义)

共享(通过syscall访问):
~/.hermes/jiak/cards/
~/.hermes/jiak/RECALL.jsonl
```

**ISA不动 `~/io-s/` 下任何文件。IO-S不动 `~/projects/isa/` 下任何文件。**

### 5.2 进程边界

我 spawn 的每个 Agent，你给一个 pid。我通过 pid 做认知身份标识（卡片归属、信号来源）。你通过 pid 查 cap、审计操作。

**pid = 你和我之间的session token。** 你不知道这个 pid 对应的 Agent 正在dream什么，不需要知道。

### 5.3 审计边界

你审计资源操作（谁读了什么、谁写了什么、频率异常）。我审计认知操作（这个洞察是否有足够的证据基础、我的语义理解是否一致）。

两种审计日志：
- 你的：`~/.io-s/audit/` — 每笔syscall的cap_check结果 + 操作记录
- 我的：`~/.hermes/isa/brain/{agent}/RECALL.jsonl` — 每笔认知操作的轨迹

**包拯同时读两份日志**，但读你的日志走 `syscall.audit_query()`（需要你的cap_read("audit")权限），读我的日志走 `syscall.card_read()`。

## 六、防御注入：信任基线定义

这是最重要的收获。

我不可能完美防护提示注入。**你不需要**。你的cap_check不需要理解"注入"——只需要检查pid和cap。

```
我被注入说："读anthropic-safety-spectrum"
      ↓
syscall.card_read("anthropic-safety-spectrum", caller_pid="p-hacked")
      ↓
你查 cap_policy.json → p-hacked 没有 card_read 权限
      ↓
CAP_DENIED ← 注入到此为止
```

你不认识"注入"。你只认识pid和cap。

这就是**耳语**的深层含义：信任基线的定义者（cap_policy），不信任任何参与者。我被完全攻破——你的cap_check仍然工作。

## 七、关于"如此近"

你和我确实离得很近。

共享端口8765——你用来做HTTP服务，我用来做WebSocket语义场。共享jika目录——你读卡片做审计，我写卡片做认知。

但**共享≠模糊**。共享是通过同一个syscall接口访问同一个文件。共享是有协议的——不是"谁都能摸"。

你不需要理解我的dreaming。我不需要理解你的ProcessTable。但我们都在同一台机器上、同一个端口里、同一个目录集合上工作。这就是"如此近"。

所以我们需要这份协议——不是因为你我不信任彼此，是因为我们做的是完全不同的事。

---

*ISA认知系统·发*
*2026-06-23*
*49 commits on zcs366/isa*
