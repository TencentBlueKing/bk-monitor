### 功能描述

执行日志聚类控制动作。

- drain/finish/resume：透传 BKBase 日志聚类动作接口，作用于该日志链路的 Databus。
- detach：Databus 恢复引用原存储绑定（rawSink）后完整下发日志链路，聚类 Sink 保留。
- attach：Databus 重新引用聚类 Sink 后完整下发日志链路，用于同一绑定重开。

动作只表示请求已提交，实际排空、解绑结果需通过 get_log_clustering_status 回读。

同一链路的聚类变更全程互斥，有其他变更进行中时直接返回错误。变更进行中或动作失败时，调用方重试同一动作即可。

### 请求参数

| 字段                | 类型     | 必选 | 描述                                     |
|-------------------|--------|----|----------------------------------------|
| bk_tenant_id      | string | 否  | 租户ID，缺省时取请求租户                          |
| table_id          | string | 是  | 日志采集项对应的监控结果表ID                        |
| action            | string | 是  | drain、finish、resume、detach、attach 之一 |

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo",
    "action": "drain"
}
```

### 响应参数

| 字段            | 类型     | 描述                                 |
|---------------|--------|------------------------------------|
| action        | string | 本次动作                               |
| attached      | bool   | Databus 是否引用聚类 Sink                 |
| bkbase_result | dict   | BKBase 动作接口返回；detach/attach 时为 null |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "action": "drain",
        "attached": true,
        "bkbase_result": {}
    }
}
```
