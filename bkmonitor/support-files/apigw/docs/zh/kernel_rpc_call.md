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

省略 `days` 则按存储时长补充。`dry_run` 默认为 `true`，设为 `false` 后实际添加别名。
返回的 `data` 包含 `table_id`、`target_index`、`days`、`start_date`、`end_date`、`aliases` 和 `dry_run`。
参数不符合要求或 ES 更新失败时返回错误。该接口标记为 `write` 级别。

在 Django shell 中可直接调用 `es_storage.backfill_aliases(days=7, dry_run=False)`。
