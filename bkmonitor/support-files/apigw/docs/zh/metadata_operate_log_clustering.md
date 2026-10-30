### 功能描述

执行日志聚类业务开关或 Databus 引用切换。模型参数更新和 Worker 维护重启不调用本接口。

- `disable`：读取现有 LogClusteringSink，保持完整配置，仅将 `spec.clustering.enabled` 设为 `false`，通过原 `/v4/apply/` 下发。由 BKBase 内部完成已接纳日志的收尾，Databus 仍引用聚类 Sink。
- `enable`：以相同方式将 `enabled` 设为 `true`，不切换 Databus 引用。
- `detach`：本地 `attached` 设为 `false`，完整下发日志链路，使 Databus 恢复引用原存储绑定（rawSink）；保留聚类资源和绑定。
- `attach`：本地 `attached` 设为 `true`，完整下发日志链路，重新引用聚类 Sink；不隐式修改 `enabled`。

`disable/enable` 复用已有资源，不创建资源、不修改模型或过滤规则、不重下发 Databus。远端聚类资源不存在时返回错误。`enabled` 由远端资源回读，普通配置合并保留该值，不新增本地状态副本。

业务关闭顺序：`disable` → 回读并确认本次 `clustering_closed` → `detach` → 确认实际解绑 → 停止 BKFara 任务。业务重开由调用方先准备好 BKFara Worker，再 `enable`、`attach`。调用方负责分步编排；本接口不轮询或代替调用方判定完成。

动作成功只表示本次下发成功，不代表实际收尾、采用或解绑已完成；通过 `get_log_clustering_status` 回读。过滤更新直接使用 `set_log_clustering_config`，不执行这些业务关闭动作。旧 `drain/finish/resume` 动作不再支持。

同一链路的聚类变更全程互斥，有其他变更进行中时直接返回错误。动作失败时，可重试同一动作；本地 `attached` 是保存的目标引用状态，不是 Runtime 回执。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|---|---|---|---|
| bk_tenant_id | string | 否 | 租户 ID，缺省时取请求租户 |
| table_id | string | 是 | 日志采集项对应的监控结果表 ID |
| action | string | 是 | `disable`、`enable`、`detach`、`attach` 之一 |

### 请求参数示例

```json
{
    "table_id": "2_bklog.demo",
    "action": "disable"
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|---|---|---|
| action | string | 本次动作 |
| attached | bool | 本地保存的目标引用状态；disable/enable 不修改此值 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "action": "disable",
        "attached": true
    }
}
```
