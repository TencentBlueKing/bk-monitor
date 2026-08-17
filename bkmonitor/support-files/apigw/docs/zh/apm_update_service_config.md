### 功能描述

向指定 APM 服务增量绑定容器负载或蓝盾流水线，用于容器管理平台、蓝盾等内部平台向 APM 注册事件关联数据。

该接口只追加请求中显式提交的增量关系，不提供解绑能力，也不会删除服务已有的事件关系、CMDB、日志、APDEX、URI 或标签配置。相同请求按关系身份去重，串行重复调用不会产生重复数据；并发追加不承诺强一致性。

### 请求方法与路径

```text
POST /app/apm/service/update_service_config/
```

该资源是内部应用态接口，由 APIGW 校验调用应用身份并授权，无需用户登录态。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_biz_id | int | 是 | APM 应用所属业务 ID |
| app_name | string | 是 | APM 应用名 |
| service_name | string | 是 | 需要绑定关系的 APM 服务名 |
| incremental_k8s_relations | array[object] | 否 | 需要追加的容器负载关系 |
| incremental_cicd_relations | array[object] | 否 | 需要追加的蓝盾流水线关系 |

两个增量字段可以同时提交。字段未提交表示不处理该类别；显式提交空数组表示本次没有新增关系，不会清空存量数据。

#### incremental_k8s_relations 元素

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bcs_cluster_id | string | 是 | BCS 集群 ID |
| namespace | string | 是 | 命名空间 |
| kind | string | 是 | Workload 类型，如 `Deployment`、`StatefulSet` |
| name | string | 是 | Workload 名称 |

K8S 关系按 `(bcs_cluster_id, namespace, kind, name)` 去重。

#### incremental_cicd_relations 元素

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| project_id | string | 是 | 蓝盾项目 ID |
| pipeline_id | string | 是 | 流水线 ID |
| pipeline_name | string | 是 | 流水线展示名称，不参与事件查询条件 |

CICD 关系按 `(project_id, pipeline_id)` 去重。已有流水线与新增数据身份相同时保留已有记录，`pipeline_name` 不会被增量请求覆盖。

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "app_name": "checkout",
  "service_name": "checkout-api",
  "incremental_k8s_relations": [
    {
      "bcs_cluster_id": "BCS-K8S-00000",
      "namespace": "prod",
      "kind": "Deployment",
      "name": "checkout-api"
    }
  ],
  "incremental_cicd_relations": [
    {
      "project_id": "demo-project",
      "pipeline_id": "p-checkout-api",
      "pipeline_name": "checkout-api 发布流水线"
    }
  ]
}
```

### 调用约束

- 不要在同一请求中混用增量字段与 APM 内部的其他服务配置字段，混用时接口会拒绝请求。
- 调用前需确保 `bk_biz_id + app_name` 对应的 APM 应用已存在；接口允许在服务被拓扑发现前预先绑定 `service_name`。
- 关系写入成功后，事件查询侧的进程内缓存最多可能延迟约 60 秒更新。
- 如需解绑或覆盖完整事件配置，请使用 APM 自身的服务配置能力，不要用空数组表达删除。

### 响应参数

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| result | bool | 请求是否成功 |
| code | int | 返回状态码 |
| message | string | 返回信息 |
| data | null | 成功时固定为空 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": null
}
```
