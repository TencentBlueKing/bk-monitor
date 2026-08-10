### 功能描述

批量查询当前租户下的自定义指标上报协议，供监控后台刷新协议缓存使用。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|---|---|---|---|
| bk_biz_id | int | 否 | 业务 ID，默认值为 `0`，表示查询全部业务 |
| bk_data_ids | list[int] | 否 | 数据 ID 列表，省略或传空列表表示不按数据 ID 过滤 |

### 请求参数示例

```json
{
  "bk_biz_id": 0,
  "bk_data_ids": [1001, 1002]
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|---|---|---|
| bk_data_id | int | 数据 ID |
| protocol | string | 上报协议，可选值为 `json`、`prometheus` |

### 响应参数示例

```json
[
  {
    "bk_data_id": 1001,
    "protocol": "json"
  },
  {
    "bk_data_id": 1002,
    "protocol": "prometheus"
  }
]
```
