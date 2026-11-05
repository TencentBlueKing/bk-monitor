# Admin 告警策略和 Redis 只读接口

实现位于 `kernel_api/rpc/functions/admin/alarm_strategy.py`、`alarm_redis.py`、`alarm_redis_service.py`。

- `admin.alarm_strategy.list/detail` 返回策略配置；省略租户即全租户，可选租户通过 SpaceApi 的业务范围筛选。
- `admin.alarm_strategy.redis_keys` 分页查询常用缓存/队列/锁/检测点状态，不读取内容。
- `admin.alarm_redis.template_list/router_list/router_detail/node_list/node_detail` 为 read 配置查询。
- `admin.alarm_redis.node_info/node_clients/node_slowlog/key_scan/key_status/key_read` 为 inspect，只读访问已配置 Redis。

Router/Node 不使用进程 ALARM_BACKEND_CLUSTER_NAME 过滤；业务路由组与 Key 前缀保留既有配置语义，不修改全局状态。自动路由歧义显式返回候选，默认节点缺失不调用初始化函数。策略缓存沿用 cache-strategy 独立配置。禁止传入任意连接地址或任意命令。

INFO返回实例级快照，commandstats按命令名组织，errorstats/latencystats可选；Sentinel解析实际主节点。CLIENT LIST将数值字段归一为JSON数字；SLOWLOG仅返回命令名、参数数量、时间与耗时，不返回写入值和脚本。

列表默认20、最大100；SCAN默认COUNT100，保留原始游标，不将空批次视为结束。string/hash/list/set/zset内容分批读取，超过1MiB省略并标记。状态TTL -1/-2保留原值，Redis连接或类型错误不伪装成不存在。

对应 Admin 页面、完整参数和响应 JSON Schema、权限与前端30秒采样规则见 bkmonitor-admin 的 `docs/resources/alarm-redis.md` 和 `src/features/alarm-redis/schemas.ts`。本地协议测试使用隔离 Redis，不代表部署环境或 Sentinel 联调通过。


## 列表过滤和批量 Key 兼容扩展

`alarm_strategy.list` 的 strategy_id/bk_biz_id/name/source/scenario/is_enabled 支持单值或数组，字段内 OR、字段间 AND，空数组不筛选；name 按任一名称模糊匹配。详情/redis_keys 的 strategy_id 仍为单值。注册 Schema 与示例同步提供数组形式。

原 `alarm_redis.key_status/key_read` 增加 keys 数组，1–20 个完整Key，与 key/template_id 互斥；共用节点/策略/backend及读取cursor/page_size。单Key响应不变，批量返回 items，顺序保持且每Key独立error、next_cursor、内容上限，不提供事务快照。节点连接失败为请求级错误，单Key读取失败不终止整批。没有新增RPC操作。

SLOWLOG通过redis-py NEVER_DECODE按原始字节读取，仅提取命令名和参数数量，避免二进制参数在协议层UTF-8解码失败，不返回原始参数。测试覆盖隔离Redis的实际二进制慢查询、批量部分失败和游标、列表组合及旧单值兼容。
