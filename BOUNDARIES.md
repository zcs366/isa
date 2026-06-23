# ISA ↔ IO-S 共享资源边界定义
# ==============================
# 两窗口并行开发时的"不删你加"守则

## ISA独有 (IO-S不碰)
~/projects/isa/                  # ISA源码目录
~/.hermes/isa/brain/{agent}/     # Brain私有数据 (卡片/索引/RECALL)
~/.hermes/isa/channels/          # ISA信号JSONL (当前直接存储，后续走syscall)

## IO-S独有 (ISA不碰)  
~/io-s/                          # IO-S源码目录 (IO-S窗口托管)
~/.io-s/                         # IO-S运行时数据 (cap_policy/process表)
~/.io-s/signals/                 # IO-S信号审计目录

## 共享资源 (通过syscall访问，不直接摸文件)
~/.hermes/jiak/cards/*.json      # jika卡片 → syscall.card_read / card_write
~/.hermes/jiak/RECALL.jsonl      # RECALL时间线 → syscall.recall_append / recall_audit
~/.hermes/isa/channels/          # 信号JSONL → syscall.signal_send / signal_recv

## syscall抽象层
ISA代码不直接调用 open()/write_text() 操作共享资源。
ISA代码调用 syscall.card_read()/card_write()/signal_send() 等。
当前实现：本地fallback模式（直接读写文件，IO-S不存在时用）。
IO-S就绪后：syscall.py 替换为真实IO-S dispatch（cap_check + 审计）。
切换时不需要改ISA业务代码——只改syscall.py内部实现。
