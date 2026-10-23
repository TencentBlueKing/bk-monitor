# 批量查询业务场景资源与存储关联

内部应用接口：`POST /app/metadata/query_resource_storage/`。

由已完成业务权限校验的 SaaS 传入 bk_tenant_id、bk_biz_id、selectors、resources、include_runtime、page 和 page_size。BCS、主机内置资源和 recording_rule 由 Metadata 解析，其余资源引用由 SaaS 根据当前资源绑定生成。recording_rule 使用 V4 预计算规则组 ID，查询其输出结果表及 VM 存储，不包含旧版规则。resources 不是业务用户可直接传入的公共请求参数。

返回 items、total、page、page_size。items 保留场景资源、数据类别、Data ID、监控结果表、分阶段 Kafka 以及全部已关联存储。默认仅查配置；实时补充单独返回。集群不返回地址和认证信息。

完整参数、场景枚举、返回字段及共存规则见仓库文档：`docs/api/apidocs/zh_hans/query_resource_storage.md`。
