# 关联查询灰度与定义就绪

`RELATION_V1BETA3_BIZ_ID_WHITE_LIST` 只控制查询切流。新旧 UQ 接口共用的
`bkmonitorv3:entity:ResourceDefinition` 和 `RelationDefinition` 保留全部业务定义；
移出名单不会删除定义，只有 DB 中实际删除的 namespace 才从 Redis 清理。

## 生效流程

1. 使用 `GlobalConfig.save()` / `GlobalConfig.set()` 保存名单。事务提交后安排
   `refresh_entity_definition_to_redis(config_change=True)`；事务回滚不发任务。
   锁被占用或发布失败时按 30 秒间隔重试，最多 5 次；每 10 分钟定时任务继续兜底。
   直接 SQL / QuerySet.update() 不触发 save 钩子，要等待定时发布或手动运行刷新任务。
2. 发布任务直接读取持久名单，组装两类完整定义，在 Redis 事务中撤销旧 ready、
   更新定义并发送变更通知。所有命令返回成功且两类共享定义存在后，单独写入
   `bkmonitorv3:entity:v1beta3:schema_ready`，值为
   `{"biz_ids":[2],"version":"<随机版本>"}`。Redis EXEC 不提供错误回滚，
   因此 ready 必须在确认整批写入成功后写入。
3. 普通及 MCP 的即时/范围关联请求直接读取持久名单，绕过 DynamicSettings
   的进程缓存。仅当业务在名单内、ready 的完整名单与持久名单一致时走 v1beta3，
   并携带 `X-Bk-Relation-Schema-Version`；DB、Redis、ready 异常均走旧接口。
4. UQ 校验版本。该进程未加载当前版本时同步读取两类定义，拒绝损坏或缺少共享定义
   的快照，并在读取后再次核对版本。后台重载会撤销本进程的已验证标记。
   版本不匹配、provider 非 Redis 或加载失败时，在读取请求体前使用旧 handler；
   租户、空间、参数和时间保持原样，响应携带
   `X-Bk-Relation-Fallback: schema-not-ready`。
5. 移出名单后，新的 SaaS 请求立即按持久名单使用旧接口，定义继续保留。
   已经发出的请求不撤回；无版本头的显式 v1beta3 探针保持原有行为。

例如从空名单加入业务 2：发布前仍走旧接口；发布完成后，请求携带新版本，UQ
完成加载后执行新查询。移除业务 2 时，即使另一个 worker 的 settings 仍缓存 `[2]`，
持久配置也会让它回到旧接口，业务专属路径继续存在。

## 发布与验证

先部署配套 [UQ PR #1499](https://github.com/TencentBlueKing/bkmonitor-datalink/pull/1499)
的版本校验和回退能力，再部署本 PR 并开启名单。老 UQ 不识别版本头，不能提供上述就绪保证。
确认 UQ 使用 Redis SchemaProvider；static 模式下带版本头的请求始终回退旧接口。

本地回归使用 fakeredis、miniredis 和 SQLite，覆盖新增/移除名单、发布失败、真实事务
提交/回滚、MCP 参数一致性、漏通知补载、后台缓存失效及即时/范围回退。
这些测试不代替部署环境验收：仍需核对实际二进制版本、两端 Redis 连接一致、专属
业务路径、partial 消费和请求时延。动态名单直接读 DB，相关请求新增一次配置查询。
