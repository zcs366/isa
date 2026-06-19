# ISA v0.6.0 并发安全审视报告（阿瑞斯视角）

**日期**: 2026-06-16
**范围**: ChannelStore.append() | flock机制 | JSONL追加原子性 | 测试覆盖
**结论**: **中等风险 — 核心路径安全，但边界条件暴露了一个真实运行中Bug**

---

## 一、flock可靠性：『能在跨进程活下来，但有一个坑』

### 现状
```python
with open(self.events_path, "ab") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        f.write(line.encode("utf-8"))
        f.flush()
        os.fsync(f.fileno())
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
```

### 实测结果
| 测试场景 | 结果 |
|---------|------|
| 4线程×50条=200条同文件 | ✅ 零乱码零丢失 |
| 4进程×25条=100条同文件（flock真实战场） | ✅ 100条无损 |
| 10进程×100条=1000条分设备目录 | ✅ 1000条无损 |

### 发现的Bug（已修复）

**原始代码在第233-236行的「检查末尾换行」逻辑**引发 `UnicodeDecodeError`：

```python
f.seek(max(0, f.tell() - 1))
last_char = f.read(1)   # ← text mode下读1字符=尝试UTF-8解码
if last_char and last_char != "\n":
    f.write("\n")
```

**竞态条件**：线程A持有flock，seek到文件末尾-1位置。线程B刚在末尾写入了一个3字节中文字符的中间字节（如`0xa7`）。A试图从UTF-8角度decode那个字节 → 崩溃。

**修复**：改用`"ab"`（binary append mode），零seek、零read，直接写编码后的bytes：

```python
f.write(line.encode("utf-8"))
```

因为 `to_json_line()` 已经在末尾包含 `\n`（第123行），不需要额外补换行。

### NFS/网络文件系统风险（未修复，但风险可控）

flock 在 NFS/CIFS 上的行为：
- **Linux NFS**: `fcntl.flock()` 通过 `flock` 系统调用不跨NFS——NFS只认 `fcntl()` POSIX记录锁（`F_SETLK`/`F_SETLKW`）。跨NFS时 `flock` 调用可能返回成功但实际上没有锁，导致并发损坏。
- **Windows SMB/CIFS (WSL跨/mnt/写入)**: WSL的 `/mnt/c/` 走DrvFs（9P协议），flock在9P上未定义——可能存在但不可靠。

**阿瑞斯鉴定**：
```
flock 在本地ext4/btrfs上可靠 ✅
flock 在NFS上不可靠 ⚠️
flock 在WSL/mnt上未知 ❓
ISA_HOME=~/.hermes/isa
  ├─ WSL中: /home/zcs/.hermes/isa → ext4 ✅
  └─ WSL外: 不涉及NFS
```
当前部署在WSL ext4上，风险较低。

---

## 二、JSONL追加原子性边界

### 「追加+fsync」的保护范围

```
f.write(line.encode("utf-8"))   # ① 写入内核page cache
f.flush()                       # ② 刷到VFS层
os.fsync(f.fileno())            # ③ 刷到磁盘介质
```

| 故障场景 | 保护边界 |
|---------|---------|
| ①之后②之前崩溃 | 丢整行（不影响已有行） |
| ②之后③之前掉电 | 丢整行（不影响已有行） |
| ③之后崩溃 | 行已持久化 ✅ |
| 写入中③之前kill -9 | 文件末尾可能残留半行bytes → read_all跳过 |

**关键决定**：没有使用 `write+rename` 原子模式。JSONL追加天生不支持「读到一个文件要么全要么无」——读到最后一行如果是部分写入，`read_all` 在text mode下会遇上 `UnicodeDecodeError` 或读到破半行。但 `read_all` 是逐行迭代的，Python的 `open()` text mode iterator 是按行读的，如果末尾是部分写入的bytes（无`\n`结尾的那行），那行会被完整读取回来 → `json.loads()` 会报错，但已经是标准JSON解析错误而非破坏。

### 实测
通过4项原子性测试：
1. 新文件 → 1行 ✅
2. 追加已有文件 → 3/3行有效 ✅
3. 超大内容(5000+字符中文/多字节UTF-8) → 无损 ✅
4. 多线程写入同一文件 → 42/42行无损 ✅

---

## 三、merge_devices 并发风险

### 问题描述
`merge_devices()` 在遍历 `channel_dir.iterdir()` 读取各设备JSONL时是 **不加锁的**。如果在merge过程中有另一个进程在写入其中某个设备的JSONL：

```
时间线:
T1: merge_devices 打开 dev1/events.jsonl，读到第50行
T2: 另一个进程写入 dev1/events.jsonl 追加第51-52行
T1: 文件句柄已打开，仍然读到原来的50行 ← OK，不会读到损坏数据
```

**不会损坏，但可能丢失最后几行**（merge时恰好写入的信号不会被merge包含）。

### 风险评估
- 数据损坏风险：**无**（只读不写原始设备文件）
- 数据丢失风险：**低**（merge输出的merged.jsonl只是一个快照，所有原始设备JSONL还在）
- 最佳实践：merge时应该先做一轮 `os.fsync` 或停写

---

## 四、测试覆盖分析

### ✅ 已覆盖
| 测试 | 覆盖场景 | 通过 |
|------|---------|------|
| 跨线程 | 4线程×50条，同线程写同device | ✅ |
| 跨进程 | 4进程×50条，不同进程不同device | ✅ |
| 跨进程同文件 | 4进程×25条，flock保护同一jsonl | ✅ |
| 高并发10进程 | 10进程×100条=1000条 | ✅ |
| 读写并发 | 写200条+读全量反复 | ✅ |
| 原子性边界 | 空文件、追加、超大UTF-8 | ✅ |
| merge_devices | 双设备各20条 → 合并40条 | ✅ |

### ❌ 未覆盖（需填补）
1. **NFS/网络文件系统** — 当前测试只在ext4跑。NFS上flock形同虚设。
2. **掉电模拟** — 没有断电/panic测试。fsync是否真的刷到介质在WSL上需要验证（WSL的fsync → Windows → 磁盘）。
3. **merge_devices + 并发写** — merge同时有写入进程在写同一频道。
4. **超大JSONL (10万+行)** — 200/1000条级别的测试。实际PB级未见。
5. **跨线程同文件写（与测试7类似，但是4个不同thread+threading.Lock vs flock）** — 实际上flock在thread间是有冗余的，因为同一个Python进程内还有 `threading.Lock()` 保护。但跨进程的flock才是真正的护城河。

---

## 五、结论

```
整体评分: B（安全可用，有已知边界）
───────────────────────────
✅ 优势:
  - binary mode写入，零解码风险
  - fsync保证持久化
  - flock跨进程真实保护
  - 每个设备独立文件（isolated failure domain）
  
⚠️ 已知风险:
  1. NFS/SMB上flock无效
  2. WSL的fsync→Windows→磁盘路径未审计
  3. merge_devices不保证时序一致性
  
❌ 已修复Bug:
  - text mode seek+f.read(1) 在多字节UTF-8并发写入时崩溃
  → 原因：检查末尾换行的冗余逻辑
  → 修复：直接binary append，zero seek
```

**一句话总结**：对于 ISA v0.6.0 的部署场景（WSL ext4，单个Agent实例），并发安全性是可靠的。但如果哪天要跑在NFS共享存储、或者两个物理机同时写同一个频道，flock那层保护就没了——需要升级到 `fcntl.lockf()` 或编写专门的存储适配层。
