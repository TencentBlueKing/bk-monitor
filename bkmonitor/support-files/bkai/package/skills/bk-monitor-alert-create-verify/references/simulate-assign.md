# 模拟分派（写入前预览）

创建或编辑**已指定告警策略**的分派规则时，在人工确认审核里一并回放最近 6 小时告警，给出模拟分派结果。用户确认该结果后才能保存。

未指定策略的规则不做预览，只走固定提醒。删除分派组不做预览。空规则组无策略可拉，跳过预览并在审核里写明。

这是本地按草稿规则回放，不是平台已执行的分派，也不会发通知。

## 是否预览

| 草稿规则 | 预览 |
| --- | --- |
| 启用规则含 `alert.strategy_id` | 按这些策略 ID 拉最近 6 小时告警并回放 |
| 规则不含 `alert.strategy_id` | 跳过；审核里写「未指定策略，跳过模拟分派」 |
| 同一组里两种规则都有 | 只预览已指定策略的规则；未指定的仍展示固定提醒，不拉全业务告警 |
| 规则未启用 | 不参与回放 |

从已指定策略的规则中收集去重后的 `strategy_id`。没有可预览策略 ID 时整组跳过。

## MCP 怎么分

配置写入和事件预览走两套 MCP，不要混用。

| 用途 | Server 后缀 | 工具 |
| --- | --- | --- |
| 分派组 / 告警组 / 策略配置 | `alarm-handling` | `search_alarm_assign_groups`、`search_alarm_notice_groups`、`get_alarm_strategy`、`save_alarm_assign_group` |
| 告警事件预览 | `alarm` | `list_alerts`，缺维度再 `get_alert_info` |

`list_alerts` **不在** handling 上。handling 能看到策略 `alert_count` / 「告警中」，拿不到告警 ID 和 IP。

调用前读取实时 schema，并从同一目标监控网关和发布环境内发现完整 Server 名称。缺少告警事件工具、鉴权失败或连接失败时，使用宿主提供的认证入口或检查依赖配置。仍不可用则停止预览，标「模拟分派未完成」；不跨环境回退，也不把不可用描述成无历史告警。

## 预览流程

```text
1. 从启用规则收集去重后的 strategy_id
2. handling：search_alarm_strategies / get_alarm_strategy
   记下策略名、alert_count、是否告警中（交叉核对，不是事件列表）
3. 动态计算 Unix 秒：end_time=now，start_time=now-21600
4. alarm：list_alerts 按 strategy_id 拉最近 6 小时全状态
5. total 超一页则翻页，按告警 ID 去重
6. 列表缺 IP/维度且规则要用时，get_alert_info 补详情（最多 50 条）
7. 按本次将保存的启用规则本地匹配，写入同一次审核摘要
8. 等用户确认模拟结果后再 save
```

## 怎么查数据

### 1. 交叉核对（handling，可选但 0 条时必做）

`search_alarm_strategies` 或 `get_alarm_strategy`：

- `alert_count`：策略当前告警次数（列表接口口径，不是 `list_alerts` 明细）
- 策略状态「告警中」：至少有未恢复实例

这两项只能说明「平台认为有告警」，不能替代 `list_alerts`。

### 2. 拉事件列表（必须，`alarm` → `list_alerts`）

时间：

- `end_time` / `start_time` 为 **Unix 秒** 字符串，每次动态算，禁止写死或误传毫秒。
- 窗口固定最近 **6 小时**（21600 秒）。该 MCP 单次跨度上限是 **86400 秒（1 天）**，超过会参数错误；不要按巡检技能的 3 天窗口来拉。

过滤：按策略拉，不要先拉全业务再本地筛。以下仅说明字段语义，`conditions` 及其类型以实时 schema 为准：

```json
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "bk_biz_ids": ["<bk_biz_id>"],
    "start_time": "<end_time - 21600>",
    "end_time": "<当前 Unix 秒>",
    "status": ["ABNORMAL", "RECOVERED", "CLOSED"],
    "conditions": [{ "key": "strategy_id", "value": ["<strategy_id>"] }],
    "page": "1",
    "page_size": "500",
    "ordering": ["-create_time"],
    "show_overview": true,
    "show_aggs": false
  }
}
```

补充：

- `status` 用三个状态显式全查。schema 写 `[]` 表示全状态，但预览不要只依赖空数组。
- 备选过滤：`query_string` 用 Lucene `strategy_id:<strategy-id>`（字段与值之间不要空格）。不要只用全文词去碰策略名。
- `page_size` 用 schema 允许的较大值（常见上限 5000，预览默认 500）。`total` 超一页继续 `page+1`。
- 多个策略 ID 分次查询，按告警 ID 去重合并。

`get_alert_info`：`query_param.bk_biz_id` + `query_param.id`（告警 ID 来自列表）。单次预览最多补 50 条；其余标「维度不足，未完整匹配」。

### 3. 0 条时先查 MCP，再下「无告警」结论

`list_alerts` 对该策略返回 `total=0` 时，**不要立刻**写成「近期无告警可回放」。按顺序排除：

1. 完整 Server 是否属于已确认的目标监控网关和环境，当前身份是否有相应业务权限。
2. 时间是否为秒、窗口是否 ≤ 86400。
3. 检查策略过滤、状态筛选和分页是否符合实时 schema；需要交叉核对时仍限定当前业务。
4. 对照 handling 的 `alert_count` / 「告警中」，并核对其时间和统计口径。存在无法解释的矛盾时，标「模拟分派未完成」，默认不得保存。整个业务也返回 0 本身不能证明 MCP 不可用。

只有同时满足下面两条，才算「近期无告警可回放」，用户确认后可以保存：

- `list_alerts` 在正确 MCP 上对该策略 6 小时全状态为 0
- handling 侧也没有与之矛盾的 `alert_count` / 「告警中」（或用户已知该策略刚创建且尚未检测）

查询失败、server 不可用、交叉核对矛盾：审核标「模拟分派未完成」，默认不得保存；只有用户明确接受「无回放仍保存」才可继续。

截断：合并后超过 1000 条，只回放前 1000 条（创建时间新到旧），并写明截断。

## 本地匹配

只用**本次将保存的完整规则列表**（更新时含保留的旧规则）。组内按规则列表顺序，第一条同时满足全部匹配条件的**启用规则**胜出。

条件求值：

- `and` / 空：与下一条同时成立。
- `or`：任一支成立。
- `eq` / `neq` / `include` / `exclude` / `reg` / `nreg` / `issuperset` 按 [rule-spec.md](./rule-spec.md)。

告警字段映射（列表没有则看详情）：

| 分派 field | 告警取值 |
| --- | --- |
| `alert.strategy_id` | `strategy_id` |
| `alert.name` | `alert_name` / `name` |
| `ip` | `ip`、`ipv6`、`target`、`tags.bk_target_ip`、`bk_target_ip` |
| `host` | `bk_host_name`、`hostname`、`bk_host_id` |
| `bk_cloud_id` | `bk_cloud_id`、`tags.bk_target_cloud_id` |
| `labels` | `labels` / 部分 `tags` |
| `dimensions` | `tags`、详情里的 dimensions |
| `alert.metric` | `metric` / 详情 origin_alarm |
| `alert.scenario` | `scenario` |

命中 → 该规则的告警组 + `alert_severity`（0 保持原级别）。未命中 → **走策略告警组**。

限制：只回放当前草稿组，不模拟业务里其他更高优先级分派组是否先截走。在结果里写明。

## 审核输出

与人工确认审核摘要同一次返回，不得先保存再补预览。必须写明 MCP server 名和窗口。

```text
模拟分派（最近 6 小时，非真实下发）
MCP：alarm / list_alerts
窗口：<start_iso> ~ <end_iso>
策略：<id + 名称>；handling alert_count=<n> / 状态=<告警中|无>
拉取：<n> 条；截断/补详情：<无 / 说明>

汇总：
- 命中规则 <序号或条件摘要> → 告警组 <名称/ID>：<count> 条
- 未命中（将走策略告警组）：<count> 条
- 维度不足未完整匹配：<count> 条

明细（每类最多 10 条）：
告警ID | 名称 | IP/目标 | 原级别 | 命中规则 | 分派告警组 | 模拟级别

限制：未模拟其他分派组优先级截获；未真实通知。
审核项：用户已确认上述模拟结果
```

正确 MCP 上确实 0 条、且与 handling 交叉核对不矛盾时，汇总为 0，仍算一次完整预览，用户确认「近期无告警可回放」后可以保存。
