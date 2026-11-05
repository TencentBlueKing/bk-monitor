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
