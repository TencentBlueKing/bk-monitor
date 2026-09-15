# Graph V4 业务级 SurrealDBBinding 写入配置

在现有 `graph_relation_v4_data_link` ResultTableOption 中配置 `surrealdb_config`。
Option 按 `bk_tenant_id + table_id` 定位，不通过全局业务白名单选择调优值；
不同租户和业务结果表可以设置不同参数。未提供的参数不下发，保留 BKBase 默认行为。

```json
{
  "write_targets": ["vm", "surrealdb"],
  "surrealdb_config": {
    "timeout": 300,
    "window": 240,
    "concurrency": 32
  }
}
```

| Option 字段 | 下发位置 | 作用与单位 |
|---|---|---|
| timeout | SurrealDBBinding.spec.timeout | 写入超时时间，单位秒；示例为 300 秒 |
| window | SurrealDBBinding.spec.window | 顶点合并及关系有效窗口，单位秒；示例为 240 秒 |
| concurrency | SurrealDBBinding.spec.concurrency | 写入请求并发数；示例为 32 |

三个字段严格要求整数且必须大于0。拼错或额外的调优字段拒绝解析，避免静默丢失配置。

## 组装与再次下发

metadata 使用现有 Graph V4 apply 流程，从该租户/结果表 option 读取配置，同时生成
Databus 和 SurrealDBBinding。仅把三个调优字段合并到 SurrealDBBinding 的已有 spec，保留 sources、sinks、
transforms、namespace、tenant 和消费组逻辑；不向 VM 分支下发这些参数。
CMDB 定时拓扑同步和链路重建会保留已配置的 surrealdb_config，不再仅重建 write_targets。
两份资源进入同一 apply 请求，但不保证 BKBase 对跨资源更新提供原子生效。

通过现有 ResultTable.modify/option 管理流程提交更新，再执行 Graph V4 下发及回读验证。
只修改 option 数据库记录不等于运行配置已生效。删除字段表示不再显式下发，不能据此保证
BKBase 恢复默认值；要恢复指定值应显式设置并验证。配置可以保留在暂时仅 VM 写入的 option
中，之后重新启用 SurrealDB 分支时继续使用；本 PR 不修改写入目标或查询灰度。

本 PR 不部署、不改数据库、不启用灰度；参数实际生效仍需 BKBase 回读并验证写入结果。
