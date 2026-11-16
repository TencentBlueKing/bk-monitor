# 关联查询灰度与定义发布

`RELATION_V1BETA3_BIZ_ID_WHITE_LIST` 只控制关联查询路由，默认为空，通过 GlobalConfig 管理。普通及 MCP 的即时、范围查询使用同一个路由函数：名单内业务调用 `/relation/v1beta3/...`，其余调用原 URL。名单含 `-1` 时全部业务都调用 v1beta3，之后新增的业务和负 ID 的项目空间也包括在内，与其他业务灰度名单的全量约定一致；`-1` 可以与业务 ID 并存。未解析到业务（业务 ID 为 0 或缺失）的请求仍调用原 URL。请求体、租户、空间和跨空间查询身份保持原有行为。

名单通过现有 DynamicSettings 读取，变更按既有配置缓存延迟生效。旧 `GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST` 不迁移到新名单，也不再控制查询或自动创建双写链路。

## 部署顺序

1. 先将承接流量的 UQ 升级到已验收的 TimeGraph 版本，即 TencentBlueKing/bkmonitor-datalink#1499 合入后的版本。升级前核对普通模式的旧查询语义兼容性，包括超过五跳的合法关联查询。历史 UQ 也有 v1beta3 URL，但使用 SurrealDB 查询实现，不能作为本次灰度基线。
2. 再上线本次 Monitor 变更，保持新名单为空。
3. 核对定义发布、实际数据路由及查询结果后，按业务配置新名单；该环境验收通过后改为 `[-1]`，切换全部业务。

关联查询需要回退时清空名单或改回具体业务 ID，配置生效后回到旧查询 URL。需要将 UQ 整包回滚到 TimeGraph 版本之前时，先清空名单，确认承接流量的 Monitor 实例配置已生效，再回滚 UQ。

## 定义发布与存储

`ResourceDefinition` 与 `RelationDefinition` 的 Redis hash 保留全部业务定义；修改查询名单不会增删定义或触发发布。API apply/delete 沿用现有 namespace 缓存重建与通知。周期任务全量重建两类定义、清理过期 namespace，并向原有与当前 namespace 的并集发送通知，让订阅者感知删除。定义变更沿用既有最终一致性，由周期任务补齐。

周期发布直接使用 Redis client 的 `hkeys`，处理 bytes/string 字段名。任一类型读取、写入或通知失败时记录任务 failure，同时继续处理另一类型。核对 `bkmonitor_metadata_cron_task_status_total` 的任务状态和错误日志确认发布结果。

CMDB relation 同步只负责普通 RT 接入和 token 更新。新 RT 按普通流程下发；已有 SurrealDB storage 和 graph option 保留，周期任务不再补建或自动更新。通用存储管理接口继续负责显式存储管理。

## 验证

开启名单前，在实际部署环境核对：

- metadata worker 周期任务成功发布两类定义，删除 namespace 的通知能够到达 UQ。
- 普通和 MCP 的即时、范围查询在名单开启、关闭时选择预期 URL，正业务、负业务及 global 空间的请求体和身份保持一致。
- TimeGraph 版本在实际数据路由、时间范围和普通配置下返回兼容的业务结果，覆盖非空、空、错误及超过五跳的查询。
- 名单变更在承接流量的实例中生效；故障回退通过关闭名单完成。

`.github/workflows/relation-rollout.yml` 运行路由、定义发布、删除通知、存储隔离和 MCP 请求回归。发布测试同时使用 fakeredis 和临时 Unix socket 上的独立 Redis；路由/发布组与 MCP 组分进程执行。测试替换 DB/model、Celery 锁和外围服务边界，实际数据库、周期调度及业务结果由部署验收核实。
