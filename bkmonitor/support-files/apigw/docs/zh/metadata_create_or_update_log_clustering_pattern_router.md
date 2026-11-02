### 功能描述

创建或更新日志聚类 Pattern 查询路由。

查询索引固定取当前有效聚类绑定的 pattern_index，集群由聚类绑定中 patternResource 对应的 metadata ES 集群确定；
state_index 仅供 BKBase 内部恢复使用，不登记查询路由。首次登记需使用空闲的 route_table_id。重复登记只允许更新由同一源日志表在同一空间创建的 Pattern 路由。

### 请求参数

| 字段             | 类型     | 必选 | 描述                                   |
|----------------|--------|----|--------------------------------------|
| bk_tenant_id   | string | 否  | 租户ID，缺省时取请求租户                        |
| table_id       | string | 是  | 日志采集项对应的监控结果表ID，用于定位聚类绑定             |
| space_type     | string | 是  | 空间类型                                 |
| space_id       | string | 是  | 空间ID                                 |
| route_table_id | string | 是  | Pattern 路由结果表ID                       |
| data_label     | string | 否  | 数据标签                                 |
| options        | list   | 否  | 结果表选项，元素包含 name、value、value_type，不接受 time_field 或内部路由归属标记 |

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo",
    "space_type": "bkcc",
    "space_id": "2",
    "route_table_id": "bklog_index_set_24466_pattern.__default__",
    "data_label": "bklog_index_set_24466_pattern"
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

### 查询当前模板

BKBase 将当前模板保存在独立 ES 索引。文档包含 signature、pattern、distance_threshold 和 publish_revision，当前写入协议没有更新时间字段。普通 UnifyQuery ES 时间范围检索会附加 range 过滤，省略 time_field 也不能用它查询这些快照。

有对应查询权限的日志平台调用方可复用现有 `POST /api/v1/esquery/dsl/`。将登记响应的 cluster_id 作为 storage_cluster_id、index_set 作为 indices，使用不含时间条件的 ES DSL。非 ESQUERY 白名单应用还需提供源日志索引集的 index_set_id，入口按该索引集校验 SEARCH_LOG 权限。白名单应用沿用已有应用鉴权策略。index_set_id 用于鉴权，实际查询目标仍取登记响应中的集群与索引。

```json
{
    "index_set_id": 24466,
    "scenario_id": "es",
    "storage_cluster_id": 3,
    "indices": "log-clustering-24466-pattern",
    "body": {
        "size": 20,
        "_source": ["signature", "pattern", "distance_threshold", "publish_revision"],
        "query": {"match_all": {}}
    }
}
```

该示例读取当前模板。按日志时间筛选模板出现记录，需要查询带时间字段的原始日志。
