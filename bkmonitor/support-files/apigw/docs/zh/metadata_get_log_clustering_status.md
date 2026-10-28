### 功能描述

查询日志链路的聚类配置与运行状态。

返回本地保存的绑定，并原样透传 BKBase 回读的聚类 Sink、Databus 资源和日志聚类状态。
sink_referenced、raw_sink_referenced 只说明远端 Databus 配置的引用情况，不代表 Runtime 已实际采用。
远端查询失败不影响其他字段返回，错误记录在 errors 中。

### 请求参数

| 字段           | 类型     | 必选 | 描述              |
|--------------|--------|----|-----------------|
| bk_tenant_id | string | 否  | 租户ID，缺省时取请求租户   |
| table_id     | string | 是  | 日志采集项对应的监控结果表ID |

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo"
}
```

### 响应参数

| 字段                  | 类型     | 描述                                   |
|---------------------|--------|--------------------------------------|
| configured          | bool   | 是否已保存聚类配置；为 false 时不返回其他字段           |
| attached            | bool   | 本地记录的 Databus 是否引用聚类 Sink            |
| binding             | dict   | 当前有效的聚类绑定                            |
| raw_sink            | dict   | 本链路当前唯一的 ES 存储绑定引用，无法唯一确定时为 null   |
| sink                | dict   | 聚类 Sink 身份：tenant、namespace、name      |
| databus             | dict   | Databus 身份：tenant、namespace、name      |
| sink_resource       | dict   | BKBase 回读的聚类 Sink 资源，不存在时为 null      |
| databus_resource    | dict   | BKBase 回读的 Databus 资源，不存在时为 null     |
| sink_referenced     | bool   | 远端 Databus.spec.sinks 是否引用聚类 Sink     |
| raw_sink_referenced | bool   | 远端 Databus.spec.sinks 是否引用 raw_sink；raw_sink 为 null 时为 false |
| clustering_status   | dict   | BKBase 日志聚类状态接口原始返回                   |
| errors              | list   | 远端查询失败信息，元素包含 source、message          |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "configured": true,
        "attached": true,
        "binding": {"task_id": "0f1d2c3b-4a59-4e6f-8a7b-9c0d1e2f3a4b", "distance_threshold": "0.5"},
        "raw_sink": {"kind": "ElasticSearchBinding", "namespace": "bklog", "name": "bklog_2_abcdefghijklmnop"},
        "sink": {"tenant": "system", "namespace": "bklog", "name": "bkm_lcs_50010_a1b2c3d4e5f6"},
        "databus": {"tenant": "system", "namespace": "bklog", "name": "bklog_2_abcdefghijklmnop"},
        "sink_resource": {"kind": "LogClusteringSink", "metadata": {}, "spec": {}, "status": {"phase": "Ok"}},
        "databus_resource": {"kind": "Databus", "metadata": {}, "spec": {}, "status": {"phase": "Ok"}},
        "sink_referenced": true,
        "raw_sink_referenced": false,
        "clustering_status": {"boundary_ready": false, "can_unbind": false},
        "errors": []
    }
}
```
