### 功能描述

查询日志链路的聚类状态。

metadata 按 BKBase 回读的聚类 Sink 与 Databus 汇总链路状态：`ready` 表示 Databus 已引用聚类 Sink，且两者 phase 均为 Ok；`detached` 表示 Databus 已恢复引用原 ES 存储绑定，不再引用聚类 Sink。业务开关以 `enabled` 回读，本地 `attached` 仅表示目标引用状态。远端查询失败不影响其他字段返回，错误记录在 `errors` 中。

`clustering_status` 为聚类 Sink `status.message` 中的 JSON 进度，仅供停用收尾核对；普通文本或为空时为 null。

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

| 字段                | 类型     | 描述                                   |
|-------------------|--------|--------------------------------------|
| configured        | bool   | 是否已保存聚类配置；为 false 时不返回其他字段           |
| attached          | bool   | 本地保存的 Databus 目标引用状态            |
| sink              | dict   | 聚类 Sink 身份：tenant、namespace、name      |
| databus           | dict   | Databus 身份：tenant、namespace、name      |
| enabled           | bool   | 远端聚类 Sink 的 `spec.clustering.enabled`，资源不存在时为 null |
| sink_phase        | string | 远端聚类 Sink 的 `status.phase`，资源不存在时为 null |
| ready             | bool   | Databus 已引用聚类 Sink，且两者 phase 均为 Ok |
| detached          | bool   | Databus 已恢复引用原 ES 存储绑定且 phase 为 Ok |
| clustering_status | dict   | 聚类 Sink `status.message` 解析出的 JSON 对象；无进度或解析失败时为 null |
| errors            | list   | 远端查询失败信息，元素包含 source、message |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "configured": true,
        "attached": true,
        "sink": {"tenant": "system", "namespace": "bklog", "name": "bkm_lcs_50010_a1b2c3d4e5f6"},
        "databus": {"tenant": "system", "namespace": "bklog", "name": "bklog_2_abcdefghijklmnop"},
        "enabled": true,
        "sink_phase": "Ok",
        "ready": true,
        "detached": false,
        "clustering_status": null,
        "errors": []
    }
}
```
