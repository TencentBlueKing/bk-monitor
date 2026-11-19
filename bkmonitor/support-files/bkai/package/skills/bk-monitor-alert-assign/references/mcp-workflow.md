# 告警分派 MCP 编排

调用前读取目标 server/tool 最新 schema。查询与写入限定单个 `bk_biz_id`。**创建、编辑、删除在 `confirm=true` 前必须完成人工确认审核**；用户没审过本次摘要就不得保存。

客户端 server 名以工具发现为准。配置和预览不要走同一套 MCP。

## Server 分工

| 用途 | Server 后缀 | 说明 |
| --- | --- | --- |
| 分派组 / 告警组 / 策略读写 | `alarm-handling` | 配置查询与写入 |
| **模拟分派预览** | **`alarm`** | 只读。工具是 `list_alerts` / `get_alert_info`。不要用 handling 拉事件 |

仅在已确认的同一目标网关和发布环境内发现完整 Server 名称并读取实时 schema。鉴权失败时使用宿主认证入口；不可用则停止，不跨环境回退。

## 工具

| 工具 | Server | 用途 |
| --- | --- | --- |
| `search_alarm_assign_groups` | handling | 发现入口。不传 `group_ids` 列出业务全部组；写入前用 ID 精读 |
| `save_alarm_assign_group` | handling | 创建或更新一个分派组 |
| `delete_alarm_assign_group` | handling | 删除一个或多个组，`group_ids` 恒为数组 |
| `search_alarm_notice_groups` | handling | 解析规则里的告警组，编辑前 `with_detail=true` |
| `get_alarm_strategy` / `update_alarm_strategy` | handling | 读/改策略 `notice.options.assign_mode`；预览前可看 `alert_count` |
| `list_alerts` | **`alarm`** | 已指定策略时拉最近 6 小时告警做模拟分派。参数与 0 条核对见 [simulate-assign.md](./simulate-assign.md) |
| `get_alert_info` | **`alarm`** | 列表缺 IP/维度、规则又要用时补详情，单次最多 50 条 |

## 创建分派组

```text
search_alarm_assign_groups 查名称和优先级冲突
  -> search_alarm_notice_groups 解析 user_groups
  -> 绑定策略时 get_alarm_strategy
  -> 判定每条规则是否含 alert.strategy_id
  -> 已指定策略：alarm list_alerts 拉最近 6 小时并本地模拟分派（见 simulate-assign.md）
  -> 输出人工确认审核摘要（含模拟结果；未指定策略则原样提醒并跳过调试）
  -> 用户明确同意保存（含确认模拟结果）
  -> save_alarm_assign_group（不传 assign_group_id，confirm=true）
  -> search_alarm_assign_groups(group_ids) 回查
```

创建最小字段：`bk_biz_id`、`name`、`priority`、`confirm`。可以先建空 `rules`，再补规则。空规则不会分派，仍要审核后才能建组。

指令是「a 条件给 A，b 条件给 B」时：写成两条（或多条）启用规则，优先走本流程，不要改去建第二条策略。

绑定已有策略的启用规则至少包含：

- `user_groups`：已有告警组 ID 数组
- `conditions`：至少一条；已知策略时默认 `alert.strategy_id` + `eq` + `[策略ID]`，再 AND 用户条件
- `is_enabled`: `true`
- `actions`: `[{ "action_type": "notice", "is_enabled": true }]`

用户要做不绑策略的分派模板时，不要自动加 `alert.strategy_id`。审核摘要必须出现：

当前分派规则未指定告警策略，可能影响多条告警策略

人工确认后即可保存。未指定策略时不要调用 `list_alerts` 做模拟分派。

## 更新分派组

```text
search_alarm_assign_groups(group_ids)
  -> 需要改策略分派模式时 get_alarm_strategy
  -> 合并规则：保留未改规则的 id
  -> 判定每条规则是否含 alert.strategy_id
  -> 已指定策略：alarm list_alerts 拉最近 6 小时并本地模拟分派（见 simulate-assign.md）
  -> 输出人工确认审核摘要（含模拟结果；未指定策略则原样提醒并跳过调试）
  -> 用户明确同意保存（含确认模拟结果）
  -> save_alarm_assign_group(assign_group_id, confirm=true)
  -> 回查
```

更新语义：

- 未传的 `name` / `priority` / `rules` 用当前组补齐。
- **传入 `rules` 就整组替换**。`[]` 会清空全部规则。
- 更新时未出现的规则 `id` 会被删除。
- 数据链路内置组不能改。

## 删除分派组

```text
search_alarm_assign_groups 确认 ID、source、edit_allowed
  -> 人工确认审核
  -> delete_alarm_assign_group(group_ids=[...], confirm=true)
  -> 再 search 确认已不存在
```

`group_ids` 即使只删一个也用数组。内置组拒绝删除。

## 打开策略上的分派开关

```text
get_alarm_strategy
  -> 复制完整 notice（含策略告警组）
  -> 只把 options.assign_mode 设为 ["only_notice","by_rule"]
  -> update_alarm_strategy（完整对象 + config_version + confirm=true）
  -> get_alarm_strategy 回查
```

只开分派开关：保留 `only_notice` 和策略告警组，不要清空 `user_groups`，不要改成只含 `by_rule`。不要碰 `items` / `detects` 里未要求修改的字段。策略无效（如 `invalid_unit`）时先说明，避免顺手改单位或阈值。

## 错误处理

- 名称或优先级冲突：列出占用项，改名或换优先级，不覆盖其他组。
- 告警组不属于本业务或不存在：停止写入。
- 漏带旧规则 `id` 导致误删：回查发现后展示差异，等用户确认再恢复，不盲目重提。
- 写成功回查失败：报告「写入返回成功、回查未完成」。
- 未做人工确认审核就请求写入：拒绝，先出示摘要。
- 规则未含 `alert.strategy_id` 且未展示固定提醒：拒绝保存。
- 已指定策略但未给出 6 小时模拟分派、或模拟失败且用户未接受无回放：拒绝保存。
- `list_alerts` 走错 MCP 或整业务为 0、同时 handling 显示 `alert_count` / 告警中：标「模拟分派未完成」，不得写成无历史告警。
