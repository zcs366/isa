# 赫淮斯托斯审视：ISA v0.6.0 多设备方案

**审视者**: 赫淮斯托斯（工艺与工程之神）
**审视范围**: 分子目录隔离、merge时间戳排序、时钟偏差
**代码版本**: ISA v0.6.0 (isa.py)
**日期**: 2026-06-16

---

## 一、分子目录隔离 — 评分为 B+

### 设计
```
channels/<channel_name>/
  <device_id_1>/events.jsonl      ← 本设备独享写入
  <device_id_2>/events.jsonl      ← 另一个设备
  merged/events.jsonl             ← merge产物（只读快照）
```

**优势**:
1. **故障域隔离** — 一个设备的JSONL损坏不影响其他设备。这是最扎实的设计决策。
2. **零锁竞争** — 每个设备只写自己的文件，不同设备之间不存在写锁竞争。对比同文件写（原v0.5方案），这解决了最大并发瓶颈。
3. **天然标识** — 目录名就是 device_id，直接溯源。不需要元数据表。
4. **清理友好** — 弃用设备可直接删除目录，不影响频道整体。

### 问题 1a：目录名作为device_id的合法性校验
**严重度**: 中

`iterdir()` 遍历所有子目录，包括 `.` 开头目录、临时文件目录、甚至是用户误创建的任意目录。当前代码只跳过了 `merged`：

```python
if not device_dir.is_dir() or device_dir.name == "merged":
    continue
```

如果一个设备名叫 `..` 或包含 `/` 字符？虽然在文件系统中 `..` 是目录遍历，`os.path.join` 不会跨级，但：
- 如果 `ISA_DEVICE_ID=../channels/evil`，写入路径变为 `channels/main/../channels/evil/events.jsonl` → 被 `Path.mkdir` 规范化，实际写入 `channels/evil/events.jsonl`。
- `iterdir()` 本身安全（Python不展开 `..`），但 `ISA_DEVICE_ID` 来自环境变量，攻击面存在。

**建议**: `ChannelStore.__init__` 中做 device_id 合法性校验：
- 只允许 `[a-zA-Z0-9_-]+`
- 禁止 `.` 开头
- 禁止空字符串

### 问题 1b：merged 本身的递归调用风险
**严重度**: 低

```python
merged_store = ChannelStore(self.channel, "merged")
# merged_store 的 device_dir = channels/<channel>/merged/
# 如果再次调用 merged_store.merge_devices()...
# 在 iterdir 中，"merged" 被跳过 ✅（第288行）
```

当前代码正确地跳过了 `merged` 目录，所以 `merge_devices()` 在 `merged` store 上调用是安全的（空操作）。但分支逻辑可以更清晰：`merge_devices()` 应该是 `ChannelStore` 的类方法或静态方法，不依赖实例的 `device_id`。

### 问题 1c：跨平台路径大小写
**严重度**: 低

channels/ 目录名来自 `ISA_DEVICE_ID`。在 Windows/macOS（不区分大小写）上，"DeviceA" 和 "devicea" 指向同一目录，但 JavaScript/Unix 认为是两个。如果一部分设备跑在 WSL ext4（区分大小写），另一部分跑在 macOS（不区分），merge 时两个目录的事件都会包含，但其中一个是空。这不是大问题，但可能让用户困惑。

---

## 二、merge时间戳排序 — 评分为 B-

### 方案
```python
all_events.sort(key=lambda l: Signal.extract_timestamp(l))
```

其中 `extract_timestamp` 提取 `_ts` 字段（浮点 epoch 秒，毫秒精度）。

### 问题 2a：时间戳精度 = 秒级（问题最大）
**严重度**: ⚠️ **高**

`datetime.now(timezone.utc).isoformat()` 默认输出到微秒级（`2026-06-16T12:34:56.123456+00:00`），但同一毫秒内的两个事件：

```
设备A: 2026-06-16T12:34:56.123456+00:00 → _ts = 1,748,589,296.123456
设备B: 2026-06-16T12:34:56.123457+00:00 → _ts = 1,748,589,296.123457
```

在同一微秒产生的两个事件，`_ts` 完全相同。排序结果是**实现定义**的（Python `sort` 是稳定的，但输入顺序依赖 `itertdir()` 返回顺序，这个顺序是文件系统相关的、不确定的）。

**实际风险**: 设备A发一条消息，设备B在同一微秒回复。merge后回复可能在消息之前。在ISA的双向对话场景中，这种"因果倒置"会产生语义错误。

**后果**: 合并后的时间线叙事（阿佛洛狄忒视角）可能在微秒级尺度上出现乱序，丢失"谁先谁后"的因果信息。

**建议修复**:
1. **添加整体顺序号**：在每个 `_ts` 末尾附加一个纳秒级别的偏移或总序号。最简单方案：`_ts = float(f"{int(ts_epoch*1e6):020d}.{device_order:04d}")`，用浮点数表示微秒后4位设备序号。
2. **稳定的次要排序键**：当 `_ts` 相等时，用 `device_id` 作为次要排序键：
   ```python
   all_events.sort(key=lambda l: (Signal.extract_timestamp(l), json.loads(l).get("device_id", "")))
   ```

### 问题 2b：merge时只有一个排序字段
**严重度**: 中

当前 `extract_timestamp` 只读 `_ts`。如果两个事件同时间戳但不同设备，merge后相对顺序取决于 `sort` 的稳定性+`itertdir` 顺序。`itertdir` 在 ext4 上返回的是 inode 顺序（大致是文件创建顺序），在 NTFS/WSL 上则是未定义。

**后果**: 同一毫秒的"先A后B"和"先B后A"在不同机器上跑 merge 可能得到不同结果——破坏不可变性承诺。

### 问题 2c：merge是全量操作
**严重度**: 中 **（性能和增量考虑）**

`merge_devices()` 每次读取所有设备的所有行到内存，排序，写回。当单个设备 JSONL 达到 10 万行（每条约 500 字节 ≈ 50MB），全量 merge 耗时数秒，内存占用 ~500MB。如果 merge 过程中有设备在写入，merge 结果会少几行（阿瑞斯审视报告已指出）。

没有增量 merge 机制。每次跑 `isa --merge` 都是完整重做。

---

## 三、时钟偏差 — 评分为 C

这是多设备方案中最薄弱的环节。

### 问题 3a：依赖系统时钟（根本问题）
**严重度**: ⚠️ **高**

```python
self.timestamp = datetime.now(timezone.utc).isoformat()
```

没有任何时钟同步保证。两个物理设备的时间差可能：
- **同一数据中心**（NTP同步）：偏差 < 10ms — 可接受
- **同一家庭网络**（路由器NTP）：偏差 < 100ms — 风险低
- **WSL宿主切换睡眠/休眠**：偏差可达数秒甚至数分钟 — 风险高
- **树莓派+RTC电池耗尽**：偏差可达数年 — 风险极高
- **VM快照回滚**：时间可能倒退 — **最危险**

### 问题 3b：时间倒退 == 排序灾难
**严重度**: ⚠️ **高**

如果设备A的时钟快了 5 秒，设备B的时钟准确：
- 设备A 在真实时间 T 写入事件 a1，时间戳标记为 T+5s
- 设备B 在真实时间 T+3s 写入事件 b1，时间戳标记为 T+3s
- merge后：`a1`（假时间 T+5s）排在 `b1`（真时间 T+3s）**之后**
- **事实上 a1 应该在前**。因果倒置。

如果设备A的时钟倒退了（比如 NTP 校正往回调整、或 VM 快照回滚），新写入的事件时间戳可能比已有事件更早，merge后旧事件插到新事件之前——即便它们是同一台设备的连续事件。

### 问题 3c：无墙钟/逻辑时钟
**严重度**: 中

ISA v0.6.0 只用了物理时间戳（wall clock）。对于多设备分布式系统，经典方案是：
1. **Lamport时钟** — 每个设备维护一个逻辑计数器，事件附带 `(counter, device_id)`，按 `(counter, device_id)` 排序。缺点：不能反映真实时间。
2. **混合逻辑时钟（HLC）** — 物理时间+N位逻辑计数器。即使用 NTP 调整、时间跳跃也能产生单调递增的时间戳。推荐方案。
3. **版本向量** — 每个设备记录自己和其他设备看到的最大时间戳。复杂度太高，ISA用不到。

### 问题 3d：merge后时间戳标注
**严重度**: 低

merged.jsonl 中每行的 `timestamp` 保留的是原始设备的本地时间戳。merge 过程没有在任意行上标注"此时间戳来自哪个设备"（虽然 device_id 字段保留）。对于需要"全局统一时间线"的用户来说，跨设备的时间戳不能直接比较——除非他们理解时钟偏差的存在。

---

## 四、隐蔽的坑（未被前几轮审视覆盖）

### 坑 4a：merge_devices 返回的新 ChannelStore 指向 merged 目录，但这个 store 也能写入

```python
merged = graph.store.merge_devices()
merged.append(some_signal)  # ⚠️ 写入 merged/events.jsonl！
```

`merge_devices()` 返回 `ChannelStore(self.channel, "merged")`。这个 store 的 `device_id` 是 `"merged"`，它的 `append()` 会把新信号写入 `merged/events.jsonl`。下一次再跑 `merge_devices()` 时，`merged` 目录被 `itertdir` 跳过，但新写入的数据**不会**进入下一轮 merge（除非显式排除）。

这会导致：
- 用户对 merged 的误写入 → 数据在 merge 产物中但不在任何设备 JSONL 中 → 下次重新 merge 后丢失
- 这是数据丢失的静默路径

**建议**: `ChannelStore` 增加 `readonly` 属性。merged store 默认只读。或者在 `merge_devices()` 最后用 `os.chmod(merged_path, 0o444)` 设为只读。

### 坑 4b：信号去重（非 ISA 本身的问题，但影响 merge 结果）

ISA 的 `id` 用 `uuid4().hex[:12]`（12 位 hex = 48 位随机）。两次独立生成的 ID 碰撞概率约 2^-48 ≈ 3.5e-15。概率极低，但：
- 如果同一信号通过两个设备写入（比如同步机制），merge 后会出现两条 `id` 相同但 `body` 可能相同也可能不同的信号。
- ISA 目前**没有去重机制**。`id` 字段存在但仅作为标识，不在 merge 时做去重判断。

**是否要处理？依场景而定**。ISA 的信号模型宣称"写入即不可变"，所以重复的 `id` 应该保留，但搜索时可能返回两条相同内容的信号——用户会困惑。

### 坑 4c：FTS5 索引与 merge 的脱节

`merge_devices()` 之后，重建 FTS5 索引是调用了 `merged.index.rebuild()`。但：
- merged 的 FTS5 索引只索引 merged/events.jsonl
- 各设备自己的 FTS5 索引没有被删除或标记为"已过时"
- 如果搜索时不小心用了设备 store 而非 merged store，结果集会不完整

当前 `SignalGraph.search()` 只搜索自己 store 的 FTS5 索引。用户需要在搜索前确认用的是 merged store 还是 device store。

### 坑 4d：ISA_DEVICE_ID 环境变量的继承风险

```python
DEFAULT_DEVICE_ID = os.environ.get("ISA_DEVICE_ID", "local")
```

如果用户在 shell A 设置 `ISA_DEVICE_ID=device_a`，然后 fork 子进程，子进程继承环境变量。如果两个 Shell 窗口同时写同一个频道：
- Shell A: `ISA_DEVICE_ID=device_a` → 写 `channels/main/device_a/events.jsonl`
- Shell B: `ISA_DEVICE_ID=device_a`（继承）→ 也写 `channels/main/device_a/events.jsonl`
- 两个进程同时 flock 同一文件 → 保护生效 ✅ 但性能变成串行

**这不是Bug，但用户容易误以为设置了不同ID**。建议在 CLI 和文档中强调：**每个进程必须设置唯一的 `ISA_DEVICE_ID`**。

### 坑 4e：merge 输出不包含设备级元数据

merged.jsonl 中每行保留 `device_id` 字段，但 merged 目录本身没有附带元数据文件记录：
- merge 操作的时间
- merge 时各设备的事件数
- 参与 merge 的设备列表

如果某设备离线了一段时间，merge 出来的结果看起来"正常"，但用户无法判断是否所有设备的数据都包含在内。

---

## 五、综合评分与修复优先级

```
赫淮斯托斯综合评价: B- （可用但要加固）
─────────────────────────────────
分子目录隔离:     B+  ✅ 设计扎实，细节欠缺校验
merge时间戳排序:   B-  ⚠️ 需要次要排序键，否则因果倒置
时钟偏差:          C   ❌ 缺少HLC/逻辑时钟，时间倒退是真实风险
隐蔽坑:           B   ⚠️ 4个可修复，1个需文档覆盖
```

### 修复优先级（按危险程度）

| 优先级 | 问题 | 修复工作量 | 影响 |
|--------|------|-----------|------|
| P0 | 🔴 merge 排序缺少 device_id 次要键 → 因果倒置 | 1行 | 高 |
| P0 | 🔴 时间戳倒退 → merge 结果错误 | 需要 HLC 实现（~40行） | 高 |
| P1 | 🟠 merged store 可写入 → 静默数据丢失 | 3行只读保护 | 高 |
| P1 | 🟠 device_id 无合法性校验 → 路径遍历 | 5行正则校验 | 中 |
| P2 | 🟡 merge 全量操作 + 无元数据 | 增量方案较复杂 | 低 |
| P2 | 🟡 FTS5 索引与 merge 脱节 | 文档说明 | 低 |

### 最小可行加固（1小时内可完成）

```python
# 1. merge排序加次要键（P0）
all_events.sort(key=lambda l: (
    Signal.extract_timestamp(l),
    json.loads(l).get("device_id", "")
))

# 2. device_id 合法性校验（P1）
_VALID_ID = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
assert _VALID_ID.match(device_id), \
    f"非法device_id: {device_id!r}"

# 3. merged store 只读保护（P1）
class ChannelStore:
    def __init__(self, channel, device_id, readonly=False):
        self.readonly = readonly
    def append(self, signal):
        if self.readonly:
            raise RuntimeError("merged store is read-only")
```

**关于HLC（P0的时钟方案）**：建议用简单的混合逻辑时钟。核心逻辑：
- 每台设备记录 `max_physical_seen`（本机看到的最大物理时间）
- 生成时间戳时：`timestamp = max(physical_now, max_physical_seen + 1微秒)`（逻辑推进）
- merge 排序时即使物理时钟偏差，同一设备的时间戳**严格递增**，跨设备的物理时间偏差异步但不会倒退
- 这只需要 10-20 行 Python，不需要外部依赖

---

*赫淮斯托斯签：三个P0/P1问题影响核心语义，建议在 v0.6.1 修复后再promote到生产。*
