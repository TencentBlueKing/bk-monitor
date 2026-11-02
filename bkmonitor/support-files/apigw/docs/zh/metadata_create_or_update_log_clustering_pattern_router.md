### 功能描述

创建或更新日志聚类 Pattern 查询路由。

查询索引固定取当前有效聚类绑定的 pattern_index，集群由聚类绑定中 patternResource 对应的 metadata ES 集群确定；
state_index 仅供 BKBase 内部恢复使用，不登记查询路由。路由结果表、空间与选项由调用方给出，复用日志路由体系落库和推送。

### 请求参数

| 字段             | 类型     | 必选 | 描述                                   |
|----------------|--------|----|--------------------------------------|
| bk_tenant_id   | string | 否  | 租户ID，缺省时取请求租户                        |
| table_id       | string | 是  | 日志采集项对应的监控结果表ID，用于定位聚类绑定             |
| space_type     | string | 是  | 空间类型                                 |
| space_id       | string | 是  | 空间ID                                 |
| route_table_id | string | 是  | Pattern 路由结果表ID                       |
| data_label     | string | 否  | 数据标签                                 |
| options        | list   | 否  | 结果表选项，元素包含 name、value、value_type，如 time_field |

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo",
    "space_type": "bkcc",
    "space_id": "2",
    "route_table_id": "bklog_index_set_24466_pattern.__default__",
    "data_label": "bklog_index_set_24466_pattern",
    "options": [
        {"name": "time_field", "value_type": "dict", "value": "{\"name\": \"updated_at\", \"type\": \"long\", \"unit\": \"millisecond\"}"}
    ]
}
```

### 响应参数

| 字段             | 类型     | 描述                 |
|----------------|--------|--------------------|
| route_table_id | string | Pattern 路由结果表ID     |
| cluster_id     | int    | Pattern 所在 ES 集群ID |
| index_set      | string | Pattern 索引名         |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "route_table_id": "bklog_index_set_24466_pattern.__default__",
        "cluster_id": 3,
        "index_set": "log-clustering-24466-pattern"
    }
}
```
