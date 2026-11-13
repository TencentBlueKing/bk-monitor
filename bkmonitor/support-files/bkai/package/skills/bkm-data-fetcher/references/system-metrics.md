# 主机监控指标查询 Skills

## 概述

本文档提供了主机监控场景下各类指标的标准查询语句，适用于 AI Agents 进行自动化监控查询和分析。

### 查询语句格式

```
bkmonitor:system:<metric_name>[时间范围]
```

**参数说明：**
- `bkmonitor`: 监控平台标识
- `system`: 数据源类型
- `<metric_name>`: 具体的指标名称（如 cpu_summary.usage）
- `[时间范围]`: 时间窗口，如 `[1m]`(1分钟)、`[5m]`(5分钟)、`[1h]`(1小时)

---

## 1. CPU 指标

### 1.1 CPU 总览

#### CPU 总使用率
- **指标说明**: 当前消耗的 CPU 百分比
- **Metric**: `cpu_summary.usage`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:usage[1m]
```

#### CPU 空闲率
- **指标说明**: 当前空闲的 CPU 百分比
- **Metric**: `cpu_summary.idle`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:idle[1m]
```

#### CPU 等待 IO 的时间占比
- **指标说明**: CPU 等待 IO 的百分比
- **Metric**: `cpu_summary.iowait`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:iowait[1m]
```

#### CPU 虚拟机时间占比
- **指标说明**: CPU 分配给虚拟机的时间占比
- **Metric**: `cpu_summary.stolen`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:stolen[1m]
```

#### CPU 系统占用率
- **指标说明**: CPU 运行在系统程序的时间占比
- **Metric**: `cpu_summary.system`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:system[1m]
```

#### CPU 用户占用率
- **指标说明**: CPU 运行在用户程序的时间占比
- **Metric**: `cpu_summary.user`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:user[1m]
```

#### CPU 内核虚拟机占用率
- **指标说明**: CPU 内核在虚拟机上运行的占比
- **Metric**: `cpu_summary.guest`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:guest[1m]
```

#### CPU 硬中断占用率
- **指标说明**: CPU 花费在硬中断上的时间占比
- **Metric**: `cpu_summary.interrupt`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:interrupt[1m]
```

#### CPU 软中断占用率
- **指标说明**: CPU 花费在软中断上的时间占比
- **Metric**: `cpu_summary.softirq`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:softirq[1m]
```

#### CPU 低优先级程序占用率
- **指标说明**: 低优先级程序在用户态执行的 CPU 占比
- **Metric**: `cpu_summary.nice`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_summary:nice[1m]
```

### 1.2 CPU 单核

#### 单核 CPU 使用率
- **指标说明**: 当前单核 CPU 使用率百分比
- **Metric**: `cpu_detail.usage`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:usage[1m]
```

#### 单核 CPU 空闲率
- **指标说明**: 当前单核 CPU 空闲率百分比
- **Metric**: `cpu_detail.idle`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:idle[1m]
```

#### 单核 CPU 等待 IO 的时间占比
- **指标说明**: 单核 CPU 等待 IO 的百分比
- **Metric**: `cpu_detail.iowait`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:iowait[1m]
```

#### 单核 CPU 虚拟机时间占比
- **指标说明**: 单核 CPU 分配给虚拟机的时间占比
- **Metric**: `cpu_detail.stolen`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:stolen[1m]
```

#### 单核 CPU 系统占用率
- **指标说明**: 单核 CPU 运行在系统程序的时间占比
- **Metric**: `cpu_detail.system`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:system[1m]
```

#### 单核 CPU 用户占用率
- **指标说明**: 单核 CPU 运行在用户程序的时间占比
- **Metric**: `cpu_detail.user`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:user[1m]
```

#### 单核 CPU 内核虚拟机占用率
- **指标说明**: 单核 CPU 内核在虚拟机上运行的占比
- **Metric**: `cpu_detail.guest`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:guest[1m]
```

#### 单核 CPU 硬中断占用率
- **指标说明**: 单核 CPU 花费在硬中断上的时间占比
- **Metric**: `cpu_detail.interrupt`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:interrupt[1m]
```

#### 单核 CPU 软中断占用率
- **指标说明**: 单核 CPU 花费在软中断上的时间占比
- **Metric**: `cpu_detail.softirq`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:softirq[1m]
```

#### 单核 CPU 低优先级程序占用率
- **指标说明**: 低优先级程序在用户态执行的单核 CPU 占比
- **Metric**: `cpu_detail.nice`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:cpu_detail:nice[1m]
```

### 1.3 CPU 负载

#### 1 分钟平均负载
- **指标说明**: CPU 1 分钟内的平均负载
- **Metric**: `system.load.load1`
- **单位**: -
- **查询语句**:
```
bkmonitor:system:system:load:load1[1m]
```

#### 5 分钟平均负载
- **指标说明**: CPU 5 分钟内的平均负载
- **Metric**: `system.load.load5`
- **单位**: -
- **查询语句**:
```
bkmonitor:system:system:load:load5[5m]
```

#### 15 分钟平均负载
- **指标说明**: CPU 15 分钟内的平均负载
- **Metric**: `system.load.load15`
- **单位**: -
- **查询语句**:
```
bkmonitor:system:system:load:load15[15m]
```

---

## 2. 磁盘指标

### 2.1 磁盘 IO

#### 磁盘 IO 使用率
- **指标说明**: 磁盘处于活动时间的百分比
- **Metric**: `io.util`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:io:util[1m]
```

#### 磁盘写速率（次数）
- **指标说明**: 磁盘每秒写入次数
- **Metric**: `io.w_s`
- **单位**: 次/s
- **查询语句**:
```
bkmonitor:system:io:w_s[1m]
```

#### 磁盘读速率（次数）
- **指标说明**: 磁盘每秒读取次数
- **Metric**: `io.r_s`
- **单位**: 次/s
- **查询语句**:
```
bkmonitor:system:io:r_s[1m]
```

#### 磁盘 IO 写速率（字节）
- **指标说明**: 磁盘每秒写入速率
- **Metric**: `io.wkb_s`
- **单位**: KB/s
- **查询语句**:
```
bkmonitor:system:io:wkb_s[1m]
```

#### 磁盘 IO 读速率（字节）
- **指标说明**: 磁盘每秒读取速率
- **Metric**: `io.rkb_s`
- **单位**: KB/s
- **查询语句**:
```
bkmonitor:system:io:rkb_s[1m]
```

#### 设备每次 IO 平均数据大小
- **指标说明**: 每个 I/O 请求的平均大小（以扇区为单位）
- **Metric**: `io.avgrq_sz`
- **单位**: 扇区
- **查询语句**:
```
bkmonitor:system:io:avgrq_sz[1m]
```

#### 平均 IO 队列长度
- **指标说明**: 磁盘队列中等待处理的 I/O 请求平均数
- **Metric**: `io.avgqu_sz`
- **单位**: 请求数
- **查询语句**:
```
bkmonitor:system:io:avgqu_sz[1m]
```

### 2.2 磁盘空间

#### 磁盘使用率
- **指标说明**: 磁盘已用空间的百分占比
- **Metric**: `disk.in_use`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:disk:in_use[1m]
```

#### 磁盘空闲大小
- **指标说明**: 磁盘剩余空间大小
- **Metric**: `disk.free`
- **单位**: bytes
- **查询语句**:
```
bkmonitor:system:disk:free[1m]
```

#### 磁盘总空间大小
- **指标说明**: 磁盘总空间大小
- **Metric**: `disk.total`
- **单位**: bytes
- **查询语句**:
```
bkmonitor:system:disk:total[1m]
```

#### 磁盘已用空间大小
- **指标说明**: 磁盘已用的空间大小
- **Metric**: `disk.used`
- **单位**: bytes
- **查询语句**:
```
bkmonitor:system:disk:used[1m]
```

---

## 3. 进程指标

#### 总进程数
- **指标说明**: 当前总进程数
- **Metric**: `env.procs`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:env:procs[1m]
```

#### 正在运行进程数
- **指标说明**: 当前运行进程数量
- **Metric**: `env.proc_running_current`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:env:proc_running_current[1m]
```

#### 正在等待 IO 的进程数
- **指标说明**: 当前正在等待 IO 进程数量
- **Metric**: `env.procs_blocked_current`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:env:procs_blocked_current[1m]
```

---

## 4. 内存指标

### 4.1 物理内存

#### 物理内存总大小
- **指标说明**: 当前主机物理内存大小
- **Metric**: `mem.total`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:total[1m]
```

#### 物理内存空闲量
- **指标说明**: 当前主机物理内存处于空闲状态的大小
- **Metric**: `mem.free`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:free[1m]
```

#### Cache 缓存的空间大小
- **指标说明**: 当前主机物理内存用于 Cache 缓存文件的空间大小
- **Metric**: `mem.cached`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:cached[1m]
```

#### Buffer 的空间大小
- **指标说明**: 当前主机物理内存用于 Buffer 的空间大小
- **Metric**: `mem.buffer`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:buffer[1m]
```

#### 物理内存已用量
- **指标说明**: 当前物理内存已被使用的大小
- **Metric**: `mem.psc_used`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:psc_used[1m]
```

#### 共享内存使用量
- **指标说明**: 共享内存所使用的内存大小
- **Metric**: `mem.shared`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:shared[1m]
```

### 4.2 应用程序内存

#### 应用程序内存可用量
- **指标说明**: 当前主机物理内存可用于启动应用程序的内存大小
- **Metric**: `mem.usable`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:usable[1m]
```

#### 应用程序内存可用率
- **指标说明**: 当前主机物理内存可用于启动应用程序的内存百分比
- **Metric**: `mem.pct_usable`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:mem:pct_usable[1m]
```

#### 应用程序内存使用量
- **指标说明**: 当前主机物理内存被用于应用程序的大小
- **Metric**: `mem.used`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:mem:used[1m]
```

#### 应用程序内存使用占比
- **指标说明**: 当前主机物理内存被用于应用程序的占比
- **Metric**: `mem.pct_used`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:mem:pct_used[1m]
```

---

## 5. SWAP 交换空间指标

#### SWAP 空闲量
- **指标说明**: 交换空间处于空闲状态的大小
- **Metric**: `swap.free`
- **单位**: bytes
- **查询语句**:
```
bkmonitor:system:swap:free[1m]
```

#### SWAP 总量
- **指标说明**: 交换空间总大小
- **Metric**: `swap.total`
- **单位**: bytes
- **查询语句**:
```
bkmonitor:system:swap:total[1m]
```

#### SWAP 已用量
- **指标说明**: 交换空间处于使用状态的大小
- **Metric**: `swap.used`
- **单位**: bytes
- **查询语句**:
```
bkmonitor:system:swap:used[1m]
```

#### SWAP 已用占比
- **指标说明**: 交换空间处于使用状态的大小占总大小的占比
- **Metric**: `swap.pct_used`
- **单位**: %
- **查询语句**:
```
bkmonitor:system:swap:pct_used[1m]
```

#### Swap 交换进内存大小
- **指标说明**: SWAP 从硬盘到内存
- **Metric**: `swap.swap_in`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:swap:swap_in[1m]
```

#### Swap 交换出内存大小
- **指标说明**: SWAP 从内存到硬盘
- **Metric**: `swap.swap_out`
- **单位**: KB
- **查询语句**:
```
bkmonitor:system:swap:swap_out[1m]
```

---

## 6. 网络指标

### 6.1 网卡（NIC）

#### 网卡入包量
- **指标说明**: 每秒接收的包的速率
- **Metric**: `net.speed_packets_recv`
- **单位**: 个/秒
- **查询语句**:
```
bkmonitor:system:net:speed_packets_recv[1m]
```

#### 网卡出包量
- **指标说明**: 每秒发送的包的速率
- **Metric**: `net.speed_packets_sent`
- **单位**: 个/秒
- **查询语句**:
```
bkmonitor:system:net:speed_packets_sent[1m]
```

#### 网卡入流量
- **指标说明**: 网卡每秒接收的字节数
- **Metric**: `net.speed_recv`
- **单位**: bytes/s
- **查询语句**:
```
bkmonitor:system:net:speed_recv[1m]
```

#### 网卡出流量
- **指标说明**: 网卡每秒发送的字节数
- **Metric**: `net.speed_sent`
- **单位**: bytes/s
- **查询语句**:
```
bkmonitor:system:net:speed_sent[1m]
```

#### 网卡错误包
- **指标说明**: 网卡驱动程序检测到的发送或接收错误的总数
- **Metric**: `net.errors`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:net:errors[1m]
```

#### 网卡丢弃包
- **指标说明**: 网卡驱动程序丢弃的数据包总数
- **Metric**: `net.dropped`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:net:dropped[1m]
```

#### 网卡冲突包
- **指标说明**: 网卡上检测到的冲突数
- **Metric**: `net.collisions`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:net:collisions[1m]
```

#### 网卡载波丢失数
- **指标说明**: 由设备驱动程序检测到的载波损耗的数量
- **Metric**: `net.carrier`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:net:carrier[1m]
```

### 6.2 TCP 连接

#### TCP CLOSING 连接数
- **指标说明**: TCP 连接处于 closing 状态的数量
- **Metric**: `netstat.cur_tcp_closing`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_closing[1m]
```

#### TCP ESTABLISHED 连接数
- **指标说明**: TCP 连接处于 established 状态的数量
- **Metric**: `netstat.cur_tcp_estab`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_estab[1m]
```

#### TCP FIN_WAIT1 连接数
- **指标说明**: TCP 连接处于 finwait1 状态的数量
- **Metric**: `netstat.cur_tcp_finwait1`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_finwait1[1m]
```

#### TCP FIN_WAIT2 连接数
- **指标说明**: TCP 连接处于 finwait2 状态的数量
- **Metric**: `netstat.cur_tcp_finwait2`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_finwait2[1m]
```

#### TCP LAST_ACK 连接数
- **指标说明**: TCP 连接处于 last_ack 状态的数量
- **Metric**: `netstat.cur_tcp_lastack`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_lastack[1m]
```

#### TCP LISTEN 连接数
- **指标说明**: TCP 连接处于 listen 状态的数量
- **Metric**: `netstat.cur_tcp_listen`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_listen[1m]
```

#### TCP SYN_RECV 连接数
- **指标说明**: TCP 连接处于 syn_recv 状态的数量
- **Metric**: `netstat.cur_tcp_synrecv`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_synrecv[1m]
```

#### TCP SYN_SENT 连接数
- **指标说明**: TCP 连接处于 syn_sent 状态的数量
- **Metric**: `netstat.cur_tcp_synsent`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_tcp_synsent[1m]
```

### 6.3 UDP

#### UDP 接收包量
- **指标说明**: UDP 接收包量
- **Metric**: `netstat.cur_udp_indatagrams`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_udp_indatagrams[1m]
```

#### UDP 发送包量
- **指标说明**: UDP 发送包量
- **Metric**: `netstat.cur_udp_outdatagrams`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:netstat:cur_udp_outdatagrams[1m]
```

---

## 7. 时间同步指标

#### 最小时间偏移量
- **指标说明**: 查询主机提供的多个时间同步服务器地址中的最小偏移量
- **Metric**: `host_timesync_query_seconds_min`
- **单位**: seconds
- **查询语句**:
```
bkmonitor:system:host_timesync_query_seconds_min[1m]
```

#### 最大时间偏移量
- **指标说明**: 查询主机提供的多个时间同步服务器地址中的最大偏移量
- **Metric**: `host_timesync_query_seconds_max`
- **单位**: seconds
- **查询语句**:
```
bkmonitor:system:host_timesync_query_seconds_max[1m]
```

#### 平均时间偏移量
- **指标说明**: 查询主机提供的多个时间同步服务器地址中的平均偏移量
- **Metric**: `host_timesync_query_seconds_avg`
- **单位**: seconds
- **查询语句**:
```
bkmonitor:system:host_timesync_query_seconds_avg[1m]
```

#### 单次查询成功的时间服务器数量
- **指标说明**: 查询主机提供的多个时间同步服务器地址的成功个数
- **Metric**: `host_timesync_query_count`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:host_timesync_query_count[1m]
```

#### 单次查询失败的时间服务器数量
- **指标说明**: 查询主机提供的多个时间同步服务器地址的失败个数
- **Metric**: `host_timesync_query_error`
- **单位**: count
- **查询语句**:
```
bkmonitor:system:host_timesync_query_error[1m]
```

---

## 使用说明

### 1. 基本查询

当用户询问某个指标时，直接使用对应的查询语句：

**示例：**
- 用户问："查询 CPU 使用率"
- Agent 执行：`bkmonitor:system:cpu_summary:usage[1m]`

### 2. 时间范围调整

根据用户需求调整时间窗口：
- `[1m]` - 1分钟
- `[5m]` - 5分钟
- `[15m]` - 15分钟
- `[1h]` - 1小时
- `[24h]` - 24小时

**示例：**
- 查询最近5分钟的内存使用率：`bkmonitor:system:mem:pct_used[5m]`

### 3. 组合查询

当用户需要多个指标时，可以组合查询：

**示例：**
- "查看主机的 CPU、内存、磁盘使用情况"
  - `bkmonitor:system:cpu_summary:usage[1m]`
  - `bkmonitor:system:mem:pct_used[1m]`
  - `bkmonitor:system:disk:in_use[1m]`

### 4. 常见场景

#### 性能分析场景
```
# CPU 性能分析
bkmonitor:system:cpu_summary:usage[5m]
bkmonitor:system:cpu_summary:iowait[5m]
bkmonitor:system:system:load:load5[5m]

# 内存分析
bkmonitor:system:mem:pct_used[5m]
bkmonitor:system:mem:free[5m]
bkmonitor:system:swap:pct_used[5m]
```

#### 网络流量分析场景
```
# 网络流量
bkmonitor:system:net:speed_recv[1m]
bkmonitor:system:net:speed_sent[1m]

# 网络连接
bkmonitor:system:netstat:cur_tcp_estab[1m]
bkmonitor:system:netstat:cur_tcp_listen[1m]
```

#### 磁盘 IO 分析场景
```
# 磁盘 IO
bkmonitor:system:io:util[1m]
bkmonitor:system:io:rkb_s[1m]
bkmonitor:system:io:wkb_s[1m]
bkmonitor:system:io:avgqu_sz[1m]
```

### 5. 告警阈值参考

| 指标类型 | 告警阈值建议 | 严重程度 |
|---------|------------|---------|
| CPU 使用率 | > 80% | 警告 |
| CPU 使用率 | > 95% | 严重 |
| 内存使用率 | > 85% | 警告 |
| 内存使用率 | > 95% | 严重 |
| 磁盘使用率 | > 80% | 警告 |
| 磁盘使用率 | > 90% | 严重 |
| 磁盘 IO 使用率 | > 80% | 警告 |
| Load 5分钟 | > CPU核心数 | 警告 |
| Load 5分钟 | > CPU核心数 * 2 | 严重 |

---

## 附录：指标速查表

### CPU 相关
- `cpu_summary.usage` - CPU总使用率
- `cpu_summary.idle` - CPU空闲率
- `cpu_detail.usage` - 单核CPU使用率
- `system.load.load1/5/15` - 系统负载

### 内存相关
- `mem.total` - 物理内存总大小
- `mem.free` - 物理内存空闲量
- `mem.used` - 应用程序内存使用量
- `mem.pct_used` - 应用程序内存使用占比
- `swap.used` - SWAP已用量

### 磁盘相关
- `disk.in_use` - 磁盘使用率
- `disk.free` - 磁盘空闲大小
- `io.util` - 磁盘IO使用率
- `io.rkb_s` / `io.wkb_s` - 磁盘读写速率

### 网络相关
- `net.speed_recv` / `net.speed_sent` - 网卡流量
- `net.speed_packets_recv` / `net.speed_packets_sent` - 网卡包量
- `netstat.cur_tcp_estab` - TCP已建立连接数
- `net.errors` / `net.dropped` - 网卡错误和丢包

### 进程相关
- `env.procs` - 总进程数
- `env.proc_running_current` - 运行中进程数
- `env.procs_blocked_current` - 阻塞进程数

---

**文档版本**: v1.0
**更新日期**: 2025-11-12
**适用平台**: 蓝鲸监控平台
