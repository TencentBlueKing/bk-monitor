# MCP 编排流程

## 总则

- 调用前用 MCP 元工具读取 server/tool 最新 schema，不把本文参数当作实时 schema。
- 查询与写入统一限定单个 `bk_biz_id`。
- 查询结果为 0 条时停止写入；多条时展示候选；唯一命中后才能进入详情和写入。
- 生产写入传 `confirm=true` 前，用户必须已经看到并同意本次具体变更。

## 创建策略

```text
解析业务和需求
  -> 判断策略类型
     -> 单指标静态阈值：确认指标数据源
     -> 日志关键字计数阈值：发现索引集并验证检索语句
     -> 其他类型：生成需求草稿和能力缺口，停止生产写入
  -> 指标策略执行告警量与维度预览
  -> search_alarm_strategies 查重
  -> search_alarm_notice_groups
  -> 可选 search_alarm_action_configs
  -> 生成草稿和配置验证
  -> 用户确认
  -> create_alarm_strategy
  -> get_alarm_strategy 回查
  -> 用户指定分派时：绑定分派（见下文）
```

首版优先使用单指标静态阈值：

- 主机监控：`data_source_label=bk_monitor`、`data_type_label=time_series`。
- 主机结果表使用 `system.<table>`，如 `system.cpu_summary`。
- `metric_field` 只传字段名，如 `usage`。
- `detect.algorithm_type=Threshold`，同时提供比较符、阈值、触发次数和检测窗口。
- 全部目标使用空目标，具体结构以实时 schema 为准。

指标策略确认查询后、生成草稿前执行 [告警风暴与维度预览](./alert-volume-preview.md)：

```text
execute_range_query：最近1小时总序列/阈值命中/维度基数
  -> 低风险：进入草稿
  -> 中风险：扩展到24小时并二次确认
  -> 高风险：扩展到24小时，默认停止创建
     -> 用户查看完整证据后明确强制创建：允许继续
```

- `step` 与策略 `agg_interval` 保持一致。
- 先执行 `count(...)` 和 `count(count by (...)(...))`，再决定是否拉取按维度聚合的明细。
- 总序列或组合规模超过预览保护阈值时不下载全部原始序列，直接输出高风险和范围证据。
- 告警量是按历史数据回放的范围，不包含通知收敛，不得写成未来精确值。
- 指标 MCP 不可用、PromQL 失败或结果截断时标记“预估不完整”，至少按中风险处理；已有聚合证据达到高风险阈值时按高风险处理。

日志关键字告警：

```text
list_index_sets
  -> 唯一定位采集项/index_set_id
  -> get_index_set_fields
  -> search_logs 使用目标 query_string 验证最近窗口
  -> search_alarm_strategies 查找同索引、同检索或同名策略
  -> search_alarm_notice_groups(with_detail=true)
  -> 生成完整 items/detects/notice 草稿
  -> 用户确认
  -> create_alarm_strategy(confirm=true)
  -> get_alarm_strategy 回查
  -> 用户指定分派时绑定分派
```

- 固定使用 `data_source_label=bk_log_search`、`data_type_label=log`。
- `query_configs` 至少保留 `alias`、`query_string`、`index_set_id`、`result_table_id`、`agg_interval`、`agg_dimension`、`agg_condition` 和 `time_field`；具体字段以实时 schema 和同索引已有策略为准，禁止猜测物理结果表。
- 先用同一 `query_string` 调用 `search_logs`。若无数据，标记数据验证失败或让用户决定是否仍创建，不能声称查询已验证。
- 常见检测语义是每周期匹配日志数 `> 0`；`trigger_config.count` 表示触发次数，`check_window` 表示检测窗口。不要把“5 周期触发 1 次”反写成 count=5。
- 日志策略创建使用完整 `items + detects + notice`，并去除从参考策略复制出的策略级、监控项、算法、检测和通知内部 ID。
- 从已有同索引策略读取结构时只作为 payload 模板；必须替换名称、检索语句、告警级别、触发规则和告警组，保留默认通知模板前先向用户展示摘要。

## 更新策略

```text
search_alarm_strategies
  -> get_alarm_strategy
  -> 获取最新 config_version 并校验字段是否受实时 schema 支持
  -> 生成最小差异并回填嵌套必填字段
  -> 用户确认
  -> update_alarm_strategy
  -> get_alarm_strategy 回查
```

字段处理：

- 阈值：保留算法 `id/type/level/unit_prefix`，只替换目标条件。
- 触发与恢复：保留当前检测级别和未修改窗口。
- 消息模板：复制完整 `notice`，只修改对应 `signal` 的 `message_tmpl` 或 `title_tmpl`。
- 告警组：优先修改策略绑定；只有用户明确要求修改公共告警组成员时才更新告警组。
- 分派开关：复制完整 `notice`，保留策略告警组，只把 `assign_mode` 设为 `["only_notice","by_rule"]`。规则写入走分派组，不塞进策略字段，也不用分派去改策略告警组。
- 日志关键字：修改前用日志 MCP 验证新的 `query_string/index_set_id`；提交完整 `items`，保留内部 ID，并携带最新 `config_version`。
- PromQL、时序查询、`agg_dimension`、`agg_interval`：仅在 `update_alarm_strategy` 实时 schema 明确支持时修改完整 `items`，不能塞入其他字段冒充更新。
- 完整更新遇到过期 `config_version` 时重新读取和生成差异，不使用旧配置重试。

## 告警组

```text
search_alarm_notice_groups(with_detail=true)
  -> 确认唯一告警组和当前成员
  -> 查询/提示引用影响范围
  -> 保留完整通知、轮值、渠道和提醒配置
  -> 用户确认
  -> update_alarm_notice_group
  -> search_alarm_notice_groups(with_detail=true) 回查
```

注意：

- 告警组名称搜索不等于成员搜索。按成员查询时需要获取完整列表后检查成员字段。
- 公共告警组变更会影响所有关联策略。
- 当前 MCP 仅更新已有告警组，不新建。

## 创建时绑定分派

```text
get_alarm_strategy 取得 strategy_id
  -> 条件分流（a→A、b→B）优先写成多条分派规则，不拆策略
  -> search_alarm_notice_groups 解析规则目标告警组
  -> search_alarm_assign_groups 按名称/ID 定位分派组
  -> 不存在则准备新建（name + unique priority），存在则合并 rules 并保留 id
  -> 已知策略时每条新规则默认 AND alert.strategy_id；通用模板不加
  -> 判定是否未指定策略；未指定则准备固定提醒并跳过模拟分派
  -> 已指定策略：alarm 的 list_alerts 最近 6 小时并本地模拟分派（见 references/simulate-assign.md）
  -> 输出人工确认审核摘要（含模拟结果），停等用户同意保存
  -> 策略未开启分派时，把 assign_mode 设为 ["only_notice","by_rule"]，保留告警组
  -> save_alarm_assign_group(confirm=true)
  -> search_alarm_assign_groups(group_ids) 回查
```

注意：

- 分派组可新建；告警组不能新建。告警组缺失时停止。
- 名称、优先级在业务内唯一。优先级数值越大越先匹配。
- 更新时传入的 `rules` 整组替换；漏带旧 `id` 等于删除该规则。
- 空规则组不会实际分派。`is_enabled` 默认可能为 false，创建场景必须显式启用。
- 开启分派后：命中规则走分派，未命中走策略告警组。改分派不要改策略告警组。
- 创建/编辑分派必须先人工确认审核；「直接处理」不能代替审核。
- 规则不含 `alert.strategy_id` 时必须原样提示：`当前分派规则未指定告警策略，可能影响多条告警策略`。确认后才保存，且不做 6 小时模拟分派。
- 已指定策略时，审核必须带最近 6 小时模拟分派（`alarm` / `list_alerts`，见 `bkm-alert-assign` 的 simulate-assign）；用户确认模拟结果后才能保存。
- 条件分流优先走分派，不拆多条策略。
- 数据链路内置分派组不能改。复杂分派（多策略复用、删除组、升级通知）进入 `bkm-alert-assign`。

## 处理套餐

```text
search_alarm_action_configs
  -> MCP 按 ID/名称/plugin_id 二次筛选
  -> get_alarm_action_config
  -> 查询/提示引用影响范围
  -> 保留完整 execute_config
  -> 用户确认
  -> update_alarm_action_config
  -> get_alarm_action_config 回查
```

HTTP 回调处理套餐更新后只能验证配置保存结果；当前没有回调调试能力。

## 屏蔽

创建：

```text
定位策略或告警
  -> search_alarm_shields(is_active=true) 查重
  -> 明确绝对开始/结束时间和周期
  -> 用户确认
  -> create_alarm_shield
  -> get_alarm_shield 回查
```

更新：

```text
get_alarm_shield
  -> 回填 begin_time/end_time/cycle_config/shield_notice
  -> 用户确认
  -> update_alarm_shield
  -> get_alarm_shield 回查
```

解除：

```text
search_alarm_shields 或 get_alarm_shield
  -> 确认屏蔽仍生效
  -> 用户确认
  -> disable_alarm_shield
  -> search_alarm_shields 回查
```

## 错误处理

- 权限、认证、配额等确定性错误：确认一次后停止，不绕过。
- 后端兼容错误：保留原配置，改用 schema 支持的完整对象路径；不要盲目重试同一写入。
- 写入成功但回查失败：报告“写入返回成功、回查未完成”，不能报告最终配置已确认。
- 时间语义冲突：例如“到明天下午，屏蔽 8 小时”无法同时满足时，先让用户选择。
