# 查询业务场景资源与存储关联

## 请求

`POST /scene_view/query_resource_storage/`（SaaS 路径，相对于现有 REST API 前缀）

使用业务查看权限。租户由登录请求上下文提供，请求体中的租户字段不能覆盖它。接口只查询已存在的配置，不创建数据源、不修复链路、不修改存储。

```json
{
  "bk_biz_id": 100,
  "selectors": [
    {"scene": "bcs", "resource_ids": ["BCS-K8S-00001"], "data_types": ["k8s_metric", "custom_metric"]},
    {"scene": "uptime_check", "resource_ids": ["12", "34"]},
    {"scene": "recording_rule", "resource_ids": ["56"], "data_types": ["metric"]}
  ],
  "include_runtime": false,
  "page": 1,
  "page_size": 100
}
```

| 参数 | 说明 |
| --- | --- |
| bk_biz_id | 必填，业务 ID；沿用现有空间业务 ID 语义 |
| selectors | 可选，省略或空数组查询所有场景；多个条件取并集 |
| scene | 场景，取值见下表 |
| resource_ids | 可选，页面资源 ID 的字符串数组；省略或空数组表示该场景全部资源 |
| data_types | 可选，该场景的数据类别；省略或空数组表示全部类别 |
| include_runtime | 默认 false；true 时对当前页补充下游运行信息 |
| page / page_size | 默认 1 / 100，page_size 最大 1000；按关联行分页 |

| scene | resource_ids | data_types |
| --- | --- | --- |
| bcs | BCS 集群 ID | k8s_metric、custom_metric、k8s_event、custom_event、system_log、custom_log |
| plugin | 插件 ID | metric、event、process_perf、process_port |
| collect_config | 采集配置 ID | metric、event、process_perf、process_port |
| custom_metric | 时序组 ID | metric |
| custom_event | 事件组 ID | event |
| uptime_check | 拨测任务 ID | http、tcp、udp、icmp |
| apm | 应用名称 app_name | metric、trace、log、profile |
| host | 业务 ID，例如 "100" | base、process_perf、process_port、event |
| recording_rule | V4 预计算规则组 ID | metric |

全业务查询按普通插件、特殊采集项组织采集场景，不重复列出普通插件的全部采集项。显式指定 collect_config 时可查询普通采集项。仅查询业务实际关联的插件，不列举全部公共插件。未删除的停用资源仍然返回。

recording_rule 仅支持 V4 规则组，旧版预计算规则不在查询范围内。按当前租户和业务对应空间查询，返回规则组保存的输出监控结果表、VM 结果表及目标 VM 存储。resource_status 使用规则组的 desired_status（running / stopped）；已软删除（is_deleted）、已申请删除或已完成删除的规则组不返回。

## 返回

沿用现有 `{result, code, message, data}` 包装，data 为：

```json
{
  "items": [
    {
      "scene": "uptime_check",
      "resource_id": "34",
      "resource_name": "订单接口拨测",
      "resource_status": "running",
      "data_type": "http",
      "bk_data_id": 600001,
      "data_name": "uptimecheck_http_100",
      "result_table_id": "100_bkmonitor_time_series_600001.base",
      "result_table_name": "订单接口拨测",
      "kafka": [
        {
          "stage": "ingestion",
          "topic": "100_uptimecheck_http",
          "cluster": {
            "cluster_id": 12,
            "cluster_name": "business-kafka",
            "display_name": "业务 Kafka",
            "cluster_type": "kafka",
            "is_default_cluster": false
          }
        }
      ],
      "storages": [
        {
          "type": "victoria_metrics",
          "table": "100_vm_uptimecheck_http",
          "role": "storage",
          "resource_name": "uptimecheck-http-vm-binding",
          "namespace": "bkmonitor",
          "cluster": {
            "cluster_id": 23,
            "cluster_name": "business-vm-storage",
            "display_name": "业务 VM 存储",
            "cluster_type": "victoria_metrics",
            "is_default_cluster": false
          }
        }
      ],
      "errors": []
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 100
}
```

一行对应“场景资源 × 数据类别 × Data ID × 监控结果表”。同一资源可以返回多行。完全相同的关联合并；共享存储不合并不同资源行。排序依次使用场景、资源 ID、数据类别、Data ID、结果表 ID。

- kafka.stage：ingestion 是采集入口，cleaned 是清洗后 Kafka。各阶段分别展示。
- storages.type：victoria_metrics、influxdb、elasticsearch、doris、redis、argus、surrealdb、bkdata。
- storages.role：storage 是配置的存储绑定；query 是 VM 查询映射；derived 是通过结果表选项明确关联的派生 VM 表；historical 是未删除的历史存储集群记录，不代表仍在写入。
- storages.table：VM/BKBase 结果表、ES 索引配置、Doris 物理表、InfluxDB measurement 或 Redis key。InfluxDB/Redis 同时返回 database。有 InfluxDB proxy 关联时，query_cluster 与后端实例集群分开展示。
- 只有资源名但尚无物理表 ID 时，table 为 null，仍保留 resource_name 和 namespace。
- CMDB 拆分行包含 source_result_table_id。仅展示明确的拆分记录、选项和存储绑定，不按表名后缀推断。
- errors 表示该资源已知的缺失关联；已知 Data ID、结果表或集群标识仍保留。未知字段返回 null。
- recording_rule 的输出没有采集 Data ID，bk_data_id 和 data_name 为 null，正常情况下 kafka 为空；不因缺少数据源关联而报错。目标 VM 存储来自规则组保存的 dst_vm_storage_name，VM 表来自 dst_vm_table_id；目标存储未登记时保留已知表名，不通过默认集群或查询集群推断。

集群对象只包含 ID、名称、显示名、类型和默认标记。不返回地址、账号、密码、Token 或原始下游错误。非默认集群并不意味着业务独占。

## 新旧配置共存

拨测根据每条任务保存的 indepentent_dataid 解析数据源：false 使用协议对应的集中 Data ID，true 查询对应业务数据源。新建任务所用的全局开关不改变已有任务的解析结果。同业务下两种任务可以同时返回。

主机数据同时查询业务空间关联和已登记的平台内置数据，不通过当前多租户开关排除旧内置 ID。对于 1001 等公共入口，存在租户专属结果表关联时使用该关联；仅明确的内置 ID 可以回读默认租户的共享入口。其他数据源和结果表严格限定租户。

APM 使用各数据类型保存的 Data ID 与结果表关联；不会因为全局共享模式改变而重算已有应用的绑定。应用明确绑定共享池时，读取默认租户中登记的共享数据源与结果表；独立数据源使用应用所属租户，普通资源不会跨租户回退。结果表归属业务为 0 不影响按场景资源查到共享链路。

AccessVMRecord 可能只说明查询映射。接口保留所有映射，并从 V4 VM 存储绑定获取实际存储集群。只有旧查询映射时，不据此推断物理存储集群。配置记录本身不证明当前数据仍在写入。

## 实时信息与批量查询

默认仅查询本地元数据，返回的是配置关联。include_runtime=true 时增加 runtime：

- bkbase：当前结果表匹配的下游分支，包括结果表、BKBase 中间 Kafka 集群名/Topic、Doris 表名等可展示字段。
- elasticsearch：当前页结果表匹配到的实际索引名称。
- errors：下游查询失败或超时的简要提示；不影响已有配置返回。

实时结果单独返回，不覆盖配置或推断配置是否一致。共享 Data ID 下不属于当前结果表的其他分支不会混入当前行。每个元数据租户的实时请求批次最多等待 5 秒；未完成项记录超时说明，已完成项和配置结果正常返回，尚未开始的请求取消。

先解析关联并分页，再按当前页批量读取存储、VM 绑定、集群和 Topic。组装响应行不执行 SQL。重复的 BKBase 链路只查询一次；recording_rule 使用输出 VM 结果表 ID 查询运行信息并去重；同一 ES 集群的索引模式合并请求。不会逐资源调用链路详情接口。

## 内部接口

SaaS 调用 `POST /app/metadata/query_resource_storage/`，网关转发到 `POST /api/v3/meta/query_resource_storage/`。此入口沿用内部应用鉴权，不直接接收页面透传的资源引用。

内部请求在公共参数之外增加 bk_tenant_id 和 resources。每个 resource 包含 scene、resource_id、resource_name、resource_status、data_type，以及 bk_data_id / data_name / table_id 引用。expand_tables 指示是否展开该数据源已登记的结果表；is_builtin 仅用于固定内置 Data ID 的共享入口解析；is_shared 由 SaaS 根据 APM 已保存的共享池绑定填写，用于读取默认租户的共享元数据。已有明确 Data ID 时不会被数据名查询替代。BCS、主机与 recording_rule 资源在 Metadata 内解析。

无需新增数据库表或迁移。发布时需同时更新 Metadata 网关资源和 SaaS API 客户端。
