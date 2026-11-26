# kernel_rpc_call

Kernel 类 RPC 通用入口，默认隐藏。

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| func_name | string | 是 | 要调用的函数名 |
| params | object | 否 | 函数入参字典，默认 `{}` |

## 特殊协议

### 查询函数列表

```json
{
  "func_name": "__meta__",
  "params": {
    "action": "list"
  }
}
```

### 查询函数详细说明

```json
{
  "func_name": "__meta__",
  "params": {
    "action": "detail",
    "target_func_name": "info"
  }
}
```

## Admin 运维接口

调用方式与其他 Kernel RPC 相同。使用 `func_name=__meta__` 调用上面的元信息协议。`action=list` 可查找 `admin.` 函数，`action=detail` 可获取对应参数和示例。成功调用的 `result.data` 保存业务结果，`result.meta` 包含本次调用的操作名和安全级别。

| 用途 | Admin 函数 |
| --- | --- |
| 环境及模型 | `admin.environment.info`、`admin.environment.effective_setting`、`admin.db.model_list`、`admin.db.model_read` |
| 场景与元数据巡检 | `admin.space.scene_related`、`admin.metadata.related`、`admin.bcs_cluster.related`、`admin.bcs_cluster.inspect_metadata`、`admin.es_storage.check` |
| 自定义上报 | `admin.custom_report.metric_check`、`admin.custom_report.metric_sync`、`admin.custom_report.metric_registration`、`admin.custom_report.report_token` |
| 数据采样与路由 | `admin.datasource.kafka_sample` 取样，`admin.datasource.kafka_probe` 可指定 BKBase namespace；`admin.query_route.read_space_router` 查询实际 Redis 字段，`inspect_related` 和 `refresh_related` 从输入目标补齐关联路由 |
| 策略、二次确认与熔断 | `admin.alarm_strategy.inspect`、`admin.alarm_strategy.manage`、`admin.alarm_strategy.double_check_query`、`admin.alarm_strategy.double_check_manage`、`admin.circuit_breaking.manage` |
| 分派、通知与故障 | `admin.alarm_assignment.action_detail`、`config`、`notice_target`、`replay`；`admin.issue.inspect` |
| 告警 Redis | `admin.alarm_redis.cache_key`、`cache_footprint`、`config_snapshot`、`strategy_cost_snapshots`、`routing_plan`、`routing_apply` |
| ES 集群诊断 | `admin.cluster_info.list` 按 `cluster_type=elasticsearch` 列集群，`admin.cluster_info.es_capabilities` 发现支持项，`admin.cluster_info.es_diagnose` 执行诊断 |
| 平台与统一查询 | `admin.platform.query`、`admin.unify_query.catalog` 支持 `discover`、`describe`、`invoke`，包括外围平台查询和 UQ 关系查询 |
| Token 授权 | `admin.api_auth_token.query` 查询各类型授权和支持的动作，`admin.api_auth_token.manage` 执行 `grant`、`update` 或 `revoke` |

例如，查询业务 2 的容器监控链路可提交以下请求。

```json
{"func_name": "admin.space.scene_related", "params": {"bk_tenant_id": "system", "bk_biz_id": 2, "scene": "bcs"}}
```

调用范围由具体操作确定。模型读取使用模型目录声明的过滤字段，需限定租户时在支持该字段的模型上使用 `filter.bk_tenant_id`。告警 Redis 路由和熔断规则组作用于当前部署。分派回放使用当前配置与缓存。自定义上报 Token 仅对当前认证租户的数据源返回，响应标记为敏感读取。

策略、熔断、Redis 路由调整和 Token 授权管理沿用各自的确认及操作者要求。对 `type=api` 执行 `admin.api_auth_token.manage` 的 `revoke` 会禁用授权并保留空业务范围记录；原有 `admin.api_auth_token.delete` 继续执行软删除。

## 内置函数

### info

返回当前环境基础信息，包括是否启用多租户模式、监控访问地址、站点前缀等。

### admin.es_storage.backfill_aliases

为实体 ESStorage 补充从昨天往前的每日读写别名，不包含当天。`days` 默认取存储时长 `retention`，
必须为正整数且不超过 `retention`。仅适用于按天切分（`date_format=%Y%m%d`）且只有一个物理索引的表，
所有别名指向该索引，不创建或轮转物理索引。日期使用 ESStorage 的时区和时间偏移配置。

```json
{
  "func_name": "admin.es_storage.backfill_aliases",
  "params": {
    "bk_tenant_id": "system",
    "table_id": "18824_bklog.bcs_k8s_40220_ingame_streamlog_v5",
    "days": 7,
    "dry_run": true
  }
}
```

省略 `days` 则在存储时长内补充。所有候选别名均按清理任务的 `group_expired_alias` 规则过滤，
排除当前已在清理范围内的别名（包含时区、时间偏移及延迟清理天数）。`dry_run` 默认为 `true`，设为 `false` 后实际添加别名。
返回的 `data` 包含 `table_id`、`target_index`、`days`、`start_date`、`end_date`、`aliases` 和 `dry_run`。
`days` 和日期范围反映过滤后的实际结果；没有可补充别名时 `days=0`、日期为 `null`，不提交 ES 更新。
参数不符合要求或 ES 更新失败时返回错误。该接口标记为 `write` 级别。

在 Django shell 中可直接调用 `es_storage.backfill_aliases(days=7, dry_run=False)`。
