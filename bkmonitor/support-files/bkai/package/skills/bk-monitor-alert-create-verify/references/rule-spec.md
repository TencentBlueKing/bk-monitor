# 分派规则字段

以实时 schema 为准。下列为已验证的常用口径。

## 规则结构

| 字段 | 说明 |
| --- | --- |
| `id` | 已有规则 ID。更新时要保留的规则必须带回，否则会被删 |
| `is_enabled` | 是否启用。默认可能 false，要生效写 `true` |
| `user_groups` | 告警组 ID 列表，至少 1 个，来自 `search_alarm_notice_groups` |
| `conditions` | 匹配条件，至少 1 条 |
| `actions` | `notice` 或 `itsm`；`itsm` 需要 `action_id` |
| `alert_severity` | 0 保持，1 致命，2 预警，3 提醒 |
| `additional_tags` | `[{key, value}]`，追加到命中告警 |
| `user_type` | 回查常见 `main` / `follower`；创建可不传 |

## 条件

每条：`field`、`value`（字符串数组）、可选 `method`（默认 `eq`）、可选 `condition`（与下一条：`and` / `or` / `""`）。

### field

| field | 用途 |
| --- | --- |
| `alert.strategy_id` | 绑定某条策略，value 为策略 ID 字符串 |
| `alert.name` | 告警名称 |
| `alert.metric` | 指标 |
| `alert.scenario` | 场景，如 `os` |
| `alert.event_source` | 事件来源，如 `bkmonitor` |
| `ip` | 主机 IP，常配合 `reg` / `nreg` |
| `host` | 主机名 |
| `bk_cloud_id` | 云区域 |
| `set` / `module` | 集群 / 模块 |
| `labels` | 标签 |
| `dimensions` | 维度 |
| `notice_users` | 通知人 |
| `is_empty_users` | 是否空接收人 |

绑定「这一条策略」时，把 `alert.strategy_id` 放在第一条，`condition` 设为 `and`。

**是否配置了策略规则**：只看 `conditions` 里有没有 `field=alert.strategy_id`。`alert.name`、`alert.metric`、IP、标签都不算已指定告警策略。

未配置时，保存前必须原样提示：

当前分派规则未指定告警策略，可能影响多条告警策略

同时跳过 6 小时模拟分派。用户确认后可以保存，不要偷偷补 `strategy_id`。已知当前策略且用户不是在做通用模板时，草稿阶段应主动带上 `strategy_id`，避免走到这条提醒。

### method

| method | 含义 |
| --- | --- |
| `eq` / `neq` | 等于 / 不等于 |
| `include` / `exclude` | 包含 / 排除 |
| `reg` / `nreg` | 正则匹配 / 不匹配 |
| `issuperset` | 超集 |

按用户明确的 IP 前缀构建规则：`field=ip`、`method=reg`、`value=["^<ip-prefix>"]`。`<ip-prefix>` 仅为占位符，必须替换为用户确认的前缀，并转义正则元字符；按 IPv4 段匹配时还需明确段边界。其余 IP 使用同一正则和 `nreg`。

## 优先级

- 业务内唯一。
- 越大越先匹配。
- 写入前列出已占用值；冲突则改候选，不覆盖。
- 高优先级 + 无 `strategy_id` 的规则会按条件命中业务内多条策略。必须先走人工确认审核，并展示固定提醒，确认后才保存。

## 动作与升级

- 通知分派：`action_type=notice`。
- ITSM：`action_type=itsm` 且提供处理套餐 `action_id`。
- `upgrade_config.user_groups` 不能与规则本身的 `user_groups` 重叠。

## 策略侧开关

分派规则写好但策略 `assign_mode` 只有 `only_notice` 时，该策略不会走分派，告警一律走策略告警组。给指定策略开启分派时，补上 `by_rule` 并保留 `only_notice` 和原告警组。不要改成只含 `by_rule`。
