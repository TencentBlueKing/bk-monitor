# Graph V4 业务级 SurrealDB 写入配置

在现有 `graph_relation_v4_data_link` ResultTableOption 中配置 `surrealdb_config`。
Option 按 `bk_tenant_id + table_id` 定位，不通过全局业务白名单选择调优值；
不同租户和业务结果表可以设置不同参数。未提供的参数不下发，保留 BKBase 默认行为。

```json
{
  "write_targets": ["vm", "surrealdb"],
  "surrealdb_config": {
    "batch": {"max_events": 1000, "timeout_secs": 1},
    "request": {"concurrency": 16},
    "vertexDebounceSecs": 240,
    "heartbeatGapMs": 300000
  }
}
```

| Option 字段 | 下发位置 | 作用与单位 |
|---|---|---|
| batch.max_events | Databus.spec.batch.max_events | 单批最大事件数；不是字节数，增大可能提高单批内存和处理耗时 |
| batch.timeout_secs | Databus.spec.batch.timeout_secs | 批次未满时的等待上限，秒；不是数据库请求超时 |
| request.concurrency | Databus.spec.request.concurrency | 该 Graph Databus 的下游写请求并发上限；不是 Kafka 分区数或 UQ 查询并发 |
| vertexDebounceSecs | Databus.spec.vertexDebounceSecs | BKBase 内顶点写入合并/节流窗口，秒；0 不增加合并等待，末次刷新等具体机制由 BKBase 实现 |
| heartbeatGapMs | SurrealDBBinding.spec.heartbeatGapMs | fn::upsert_relation 的关系心跳有效期与连续段阈值，毫秒；300000 为五分钟 |

字段遵循 BKBase 协议：`vertexDebounceSecs`、`heartbeatGapMs` 为小驼峰，
`batch` 内保留 `max_events` / `timeout_secs`。所有值严格要求整数；批量、等待、并发、
关系窗口须大于0，顶点合并窗口可为0。拼错的调优字段拒绝解析，避免静默丢失配置。

## 组装与再次下发

metadata 使用现有 Graph V4 apply 流程，从该租户/结果表 option 读取配置，同时生成
Databus 和 SurrealDBBinding。仅把调优字段合并到已有 spec，保留 sources、sinks、
transforms、namespace、tenant 和消费组逻辑；不向 VM 分支下发这些参数。
CMDB 定时拓扑同步和链路重建会保留已配置的 surrealdb_config，不再仅重建 write_targets。
两份资源进入同一 apply 请求，但不保证 BKBase 对跨资源更新提供原子生效。

通过现有 ResultTable.modify/option 管理流程提交更新，再执行 Graph V4 下发及回读验证。
只修改 option 数据库记录不等于运行配置已生效。删除字段表示不再显式下发，不能据此保证
BKBase 恢复默认值；要恢复指定值应显式设置并验证。配置可以保留在暂时仅 VM 写入的 option
中，之后重新启用 SurrealDB 分支时继续使用；本 PR 不修改写入目标或查询灰度。

## 关系函数的配套边界

BKBase 仍需识别 `SurrealDBBinding.spec.heartbeatGapMs`，在正确 namespace/database 中更新
数据库参数（例如 `$graph_heartbeat_gap_ms`），供五参数 `fn::upsert_relation` 读取。
metadata 不执行 SurrealDB DDL，也不重写历史关系段。存储参数名称不属于 BKBase JSON 命名约定。
增大关系有效窗口会延迟关系失效，不会消除每次不同关系心跳的 UPDATE；
顶点节流和关系有效期不能混为一项配置，也不能仅用调大阈值证明写入性能已改善。

动态改变关系窗口前，BKBase/函数侧必须明确已有关系段的版本或生效时间语义，验证阈值增大、
缩小、重复心跳、跨段与已有数据的行为。必须回读实际值并核验写入结果后才可宣称热调参成功。
本 PR 不部署、不改数据库、不启用灰度；函数参数落库与切换语义仍为配套依赖。
