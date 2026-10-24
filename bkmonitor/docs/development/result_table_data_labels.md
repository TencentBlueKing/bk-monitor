# ResultTable 数据标签与插件 V4 迁移

`ResultTable.data_labels` 是完整标签列表，Python 标签筛选及查询路由只读取这个字段。
`data_label` 暂时保留原有 128 字符类型，用于尚未升级的 BMW。

- 创建和修改接口同时接受 `data_labels` 数组以及旧 `data_label` CSV 字符串；同时传入时以数组为准。
- 标签能够在 128 字符内完整拼接时同步两个字段；超长时保留原 `data_label`，只更新数组。
- 新建结果表的标签超长时，旧字符串留空；显式传入空数组会清空两个字段。
- 结果表及自定义上报接口返回两个字段，旧 `data_label` 保留实际存储值，完整标签从 `data_labels` 读取。
- migration 按逗号拆分已有标签，空值转为空数组，旧字段内容保持不变。
- Redis 的标签到 RT 映射及详情中的字符串协议保持原样，内容从新数组生成。
- 插件编辑仍传入基础标签时，已迁移 V4 插件的旧分表别名继续保留；显式数组可以替换或清空。

## 上线

先执行 `python manage.py migrate metadata --database=monitor_api`，再切换 Python 进程。
如环境配置了其他 Metadata 数据库别名，应使用该别名。
迁移仅搬迁已有标签；旧分表 RT 的查询别名由插件迁移命令补充。
旧 Python 进程若仍只写旧字段，会导致数组遗漏后续变更，应在停止旧写入后完成数据搬迁并切换版本。
BMW 在列表超长时继续读取旧字符串，新增的超长别名通过 Python 发布的路由生效。

## 管理命令

```bash
python manage.py migrate_plugin_v4 precheck --bk-tenant-id system --bk-data-id 50010 --bk-biz-id 2
python manage.py migrate_plugin_v4 pre-run --bk-tenant-id system --bk-data-id 50010 --bk-biz-id 2
python manage.py migrate_plugin_v4 execute --bk-tenant-id system --bk-data-id 50010 --bk-biz-id 2
python manage.py migrate_plugin_v4 status --bk-tenant-id system --bk-data-id 50010 --bk-biz-id 2
```

`precheck` 和 `pre-run` 只读；计划中给出完整 `data_labels`、标签拼接长度和是否同步旧字段。
默认沿用 `__default__` 已接入的 VM 集群，也可通过 `--vm-cluster-name` 指定。
旧表发现结合 Data ID 关系和同插件前缀，排除 CMDB 中间表，并按租户过滤。

`execute` 注册现有 Data ID、沿用 Kafka Topic 和 Transfer 消费组申请链路。
组件全部达到 `Ok` 后写入别名并发布路由，最后标记 BKBase 来源并删除 Transfer Consul 配置。
BKBase 申请是异步且不属于数据库事务；中断后可能已创建部分资源，可检查 `status` 后重试。
旧分表的存储映射保持不变，用于查询历史数据。

`status` 检查组件、Transfer 配置、标签路由、结果表及空间路由；没有上报数据不单独判为异常。
此命令不回填历史数据，也不执行线上迁移，只有运行 `execute` 才会提交环境配置。
