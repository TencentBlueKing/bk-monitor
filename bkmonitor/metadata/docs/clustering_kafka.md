# 聚类 Kafka 解析规范与计划

2026-11-19，待代码 review，未发布。

日志平台选择 metadata ClusterInfo 的 Kafka 集群 ID。新增后端接口 `GET /app/metadata/resolve_clustering_kafka/`，参数 `bk_tenant_id`、`cluster_id`。查询同租户 Kafka 和日志 namespace 中已同步的 KafkaChannel；返回集群 ID、KafkaChannel 引用及 librdkafka 连接配置。复用网关应用认证，不对浏览器开放凭证。查询不自动注册、创建 Topic 或变更集群。

日志平台将 ID 传给 Runtime 创建接口，取得 Topic/消费组及 KafkaChannel 引用，再下发 Databus。BKBase 只引用 KafkaChannel。连接依据 metadata 已成功同步的 KafkaChannel 连接快照；不得用全局默认覆盖该集群 SASL 配置。

实施计划：

- [x] resolver、API 客户端、后端路由和网关声明。
- [x] 移除日志平台的连接查询客户端。解析接口供 bkfara Runtime 通过应用授权调用。
- [x] 租户、已注册映射、明文／SCRAM、未同步字段及单租户默认值单元回归。
- [ ] PR review 和各环境的网关同步／资源授权。
- [ ] 日志平台新业务链路采用请求；发布后完整业务联调。

只提交 PR，不发布，不迁移资源。

单租户的 metadata 租户 system 与 BKBase 默认 tenant 不混用：返回引用省略 tenant，交给 BKBase 原生默认值。多租户返回实际 tenant。日志平台负责新链路的业务接入。创建任务时提交 ID，拿到公开的 KafkaChannel 引用后下发 Databus。下发失败时保留任务 ID，用同一创建幂等键恢复调用。

验证：11 项隔离单元测试通过；覆盖已同步认证快照，防止未同步的 ClusterInfo 修改分裂两端连接。Python 语法和网关后端路径／认证声明检查通过。ORM 与外部服务使用模拟对象，未运行完整 metadata 数据库测试、实际网关授权或业务 E2E。
