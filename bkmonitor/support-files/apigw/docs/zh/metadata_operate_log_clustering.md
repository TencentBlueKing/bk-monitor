### 功能描述

执行日志聚类控制动作。

- drain/finish/resume：透传 BKBase 日志聚类动作接口，作用于该日志链路的 Databus。
- detach：Databus 恢复引用原存储绑定（rawSink）后完整下发日志链路，聚类 Sink 保留。
- attach：Databus 重新引用聚类 Sink 后完整下发日志链路，用于同一绑定重开。

动作只表示请求已提交，实际排空、解绑结果需通过 get_log_clustering_status 回读。

每次动作都会推进配置版本，且版本在调用 BKBase 之前提交：动作失败后须使用同一 operation_id 重试（按重放处理并重新执行动作）；
如需改用新的 operation_id，先通过 get_log_clustering_status 读取当前 revision 作为 expected_revision。

### 请求参数

| 字段                | 类型     | 必选 | 描述                                     |
|-------------------|--------|----|----------------------------------------|
| bk_tenant_id      | string | 否  | 租户ID，缺省时取请求租户                          |
| table_id          | string | 是  | 日志采集项对应的监控结果表ID                        |
| operation_id      | string | 是  | 操作ID；同一操作重试（含动作失败后的重试）时保持不变             |
| expected_revision | int    | 是  | 期望的当前配置版本，与当前版本不一致时拒绝                  |
| action            | string | 是  | drain、finish、resume、detach、attach 之一 |

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo",
    "operation_id": "disable-24466-0001-drain",
    "expected_revision": 1,
    "action": "drain"
}
```

### 响应参数

| 字段            | 类型     | 描述                                 |
|---------------|--------|------------------------------------|
| revision      | int    | 当前配置版本                             |
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
        "revision": 2,
        "action": "drain",
        "attached": true,
        "bkbase_result": {}
    }
}
```
