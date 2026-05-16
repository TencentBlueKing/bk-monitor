# V4 Recording Rule 预计算方案

## 背景

Metadata 当前已有 `RecordRule` 预计算链路，主要面向 bkbase V3 计算 flow：

- `RecordRule` 保存规则、源 VM RT、目标 VM RT、计算频率和状态。
- `ResultTableFlow` 负责拼装 V3 flow 的 source / promql_v2 / vm_storage 节点，并调用 bkdata V3 flow API。
- 规则解析依赖 `unify_query.promql_to_struct` / `struct_to_promql`，最终生成 V3 flow 可消费的 SQL 配置。

新的预计算模块面向 bkbase V4 链路，入口不再直接复用旧的 SQL 转换逻辑，而是先通过 unify-query 的 check 接口做只解析、只预览的路由与 MetricQL 生成，再基于返回信息创建 V4 recording rule flow。

## Unify Query 解析预览

V4 预计算支持两种用户输入方式，分别对应 unify-query 的两个 check 接口：

| 输入方式 | SaaS API Resource | unify-query path | 说明 |
| --- | --- | --- | --- |
| 结构化 QueryTs | `api.unify_query.check_query_ts` | `POST /check/query/ts` | 直接提交 `query_list`、`metric_merge`、时间范围等结构化参数 |
| PromQL | `api.unify_query.check_query_ts_by_promql` | `POST /check/query/ts/promql` | 提交 PromQL，由 unify-query 内部转换成 QueryTs 后走同一套 check 逻辑 |

公共 header 由 SaaS API wrapper 处理，check resource 暂不额外暴露公共 header 透传参数：

- `Content-Type: application/json`
- `X-Bk-Scope-Space-Uid`: 优先由 `space_uid` 入参推导，或沿用现有 wrapper 从请求上下文、`bk_biz_ids` 推导的逻辑
- `X-Bk-Scope-Skip-Space`: 沿用现有全局空间逻辑

### 结构化 QueryTs

必填字段：

- `query_list`
- `start_time`
- `end_time`

当前 SaaS resource 暴露的可选字段：

- `metric_merge`
- `step`
- `space_uid`
- `timezone`
- `instant`
- `reference`
- `not_time_align`
- `limit`

最小请求示例：

```json
{
  "space_uid": "bkcc__<BK_BIZ_ID>",
  "query_list": [
    {
      "data_source": "bk_monitor",
      "table_id": "<RESULT_TABLE_ID>",
      "field_name": "<METRIC_NAME>",
      "is_regexp": false,
      "function": [
        {
          "method": "avg",
          "dimensions": ["bk_target_ip"]
        }
      ],
      "time_aggregation": {
        "function": "avg_over_time",
        "window": "1m"
      },
      "conditions": {
        "field_list": [
          {
            "field_name": "bk_biz_id",
            "value": ["<BK_BIZ_ID>"],
            "op": "eq"
          }
        ],
        "condition_list": []
      },
      "table_id_conditions": [],
      "reference_name": "a"
    }
  ],
  "metric_merge": "a",
  "start_time": "1710000000",
  "end_time": "1710000600",
  "step": "1m",
  "timezone": "Asia/Shanghai",
  "instant": false,
  "reference": false,
  "not_time_align": false,
  "limit": 0
}
```

### PromQL

必填字段：

- `promql`
- `start`
- `end`

当前 SaaS resource 暴露的可选字段：

- `step`
- `bk_biz_ids`
- `limit`
- `slimit`
- `match`
- `is_verify_dimensions`
- `reference`
- `not_time_align`
- `down_sample_range`
- `timezone`
- `look_back_delta`
- `instant`
- `add_dimensions`

最小请求示例：

```json
{
  "promql": "avg by (bk_target_ip) (avg_over_time(<METRIC_NAME>{bk_biz_id=\"<BK_BIZ_ID>\"}[1m]))",
  "start": "1710000000",
  "end": "1710000600",
  "step": "1m",
  "instant": false,
  "timezone": "Asia/Shanghai",
  "look_back_delta": "",
  "reference": false,
  "not_time_align": false,
  "down_sample_range": "",
  "bk_biz_ids": ["<BK_BIZ_ID>"],
  "limit": 0,
  "slimit": 0,
  "match": "",
  "is_verify_dimensions": false,
  "add_dimensions": []
}
```

### 成功响应

两个接口响应结构一致：

```json
{
  "data": [
    {
      "storage_type": "victoria_metrics",
      "metricql": "avg by (bk_target_ip) (avg_over_time({bk_biz_id=\"<BK_BIZ_ID>\", result_table_id=\"<VM_RESULT_TABLE_ID>\", __name__=\"<METRIC_NAME>\"}[1m]))",
      "result_table_id": ["<VM_RESULT_TABLE_ID>"]
    }
  ]
}
```

关键约定：

- `data` 是 V4 预计算解析的唯一事实源，不能为空。
- `data[*].storage_type` 必须全部为 `victoria_metrics`。
- 单条 record 只能解析出一个最终 `metricql` 字符串。
- `data[*].result_table_id` 按 VMRT 处理，用于解析源表范围和自引用排除。
- 失败时响应可能包含 `error`；本模块仅记录错误文本。

## V4 Flow 配置

V4 recording rule flow 使用 `POST /v4/apply/` 创建，删除时使用：

```text
DELETE /v4/namespaces/bkbase/flows/{flow_name}/
```

典型 flow 配置：

```json
{
  "config": [
    {
      "kind": "Flow",
      "metadata": {
        "tenant": "default",
        "namespace": "bkbase",
        "name": "<FLOW_NAME>",
        "labels": {},
        "annotations": {}
      },
      "spec": {
        "nodes": [
          {
            "kind": "VmSourceNode",
            "name": "vm_source",
            "data": {
              "kind": "ResultTable",
              "tenant": "default",
              "namespace": "bkmonitor",
              "name": "<SOURCE_BKBASE_RESULT_TABLE_NAME>"
            }
          },
          {
            "kind": "RecordingRuleNode",
            "name": "<FLOW_NAME>",
            "inputs": ["vm_source"],
            "output": "<OUTPUT_RESULT_TABLE>",
            "config": [
              {
                "expr": "sum(rate(<METRIC_NAME>{bk_biz_id=\"<BK_BIZ_ID>\"}[1m]))",
                "interval": "1min",
                "metric_name": "<OUTPUT_METRIC_NAME>",
                "labels": [
                  {
                    "label_key": "label_value"
                  }
                ]
              }
            ],
            "storage": {
              "kind": "VmStorage",
              "tenant": "default",
              "namespace": "bkmonitor",
              "name": "<VM_STORAGE_NAME>"
            }
          }
        ],
        "operation_config": {
          "start_position": "from_head",
          "stream_cluster": null,
          "batch_cluster": null,
          "deploy_mode": null
        },
        "maintainers": ["<MAINTAINER>"],
        "desired_status": "running"
      },
      "status": null
    }
  ]
}
```

已确认约束：

- `VmSourceNode` 的源 RT 必须已有 VM storage。
- `VmSourceNode.data.name` 不是 VMRT，而是源表对应的 `ResultTableConfig.name`。
- 如果 check 返回的源 VM RT 中包含当前预计算自身的输出 RT，需要在生成 `VmSourceNode` 前排除，避免自引用计算。
- `RecordingRuleNode.inputs` 指向一个或多个 `VmSourceNode.name`。
- `RecordingRuleNode.output` 是 recording rule 产生的新 RT，需要提前在 metadata 中定义。
- `interval` 当前支持 `1min`、`2min`、`5min`、`10min`。
- series 限制口径是单个 PromQL 计算的 series 总量，当前约束按 50W 理解。
- recording rule 场景暂不需要关心 `operation_config` 细节，先按固定默认值下发。

### VMRT 到 bkbase ResultTable name 的解析

check 返回的 `result_table_id` 按 VMRT 处理，但 V4 Flow source 需要的是 bkbase ResultTable name。Metadata 解析时批量完成这层映射：

1. 优先用 `ResultTableConfig.bkbase_table_id == vm_rt` 命中源表配置，取 `ResultTableConfig.name`。
2. 未命中时，通过 `AccessVMRecord.vm_result_table_id -> result_table_id` 回退查询 `ResultTableConfig.table_id`，再取 `ResultTableConfig.name`。
3. 同时通过 `AccessVMRecord.vm_cluster_id -> ClusterInfo.cluster_name` 固化每张源 VMRT 的 VM storage。

解析结果固化在 `src_result_table_configs`：

```json
[
  {
    "result_table_id": "<RESULT_TABLE_ID>",
    "vm_result_table_id": "<VM_RESULT_TABLE_ID>",
    "bkbase_result_table_name": "<SOURCE_BKBASE_RESULT_TABLE_NAME>",
    "vm_storage_name": "<SOURCE_VM_STORAGE_NAME>"
  }
]
```

## 新预计算表

V4 按 group 建模：用户看到的是一个预计算组，组内可以包含多条逻辑 record。当前版本暂不拆分，底层只生成一个 bkbase Flow；group 统一维护输出 `table_id`、`dst_vm_table_id` 和 `dst_vm_storage_name`。

| 模型 | 事实源 | 说明 |
| --- | --- | --- |
| `RecordRuleV4` | group 当前状态 | 保存空间、租户、`group_name`、稳定 `flow_name`、统一输出 RT、generation、聚合状态、锁、当前 spec、已生效 resolved、已生效 desired status |
| `RecordRuleV4Spec` | 用户输入快照 | 保存 group 原始完整配置、计算周期、labels、用户声明版本和当前 spec 的 latest resolved |
| `RecordRuleV4SpecRecord` | 用户输入中的单条 record | 保存内部稳定 `record_key`、查询输入、输出指标名、labels、原始顺序 |
| `RecordRuleV4Resolved` | 实时解析快照 | 保存一次 unify-query check 后的 group 语义结果，是否可更新以本层 `content_hash` 为准 |
| `RecordRuleV4ResolvedRecord` | 单条 record 的解析结果 | 保存 `metricql`、`src_vm_table_ids`、源表 bkbase name、源 VM storage |
| `RecordRuleV4Flow` | 单 Flow 目标实体 | 保存某份 resolved 下生成的唯一目标 Flow、稳定 `flow_name`、Flow config、实际观测状态 |
| `RecordRuleV4Event` | 事件流水 | 保存用户操作、resolve、apply、flow action、flow observe 的结构化历史 |

索引约束：

- `(bk_tenant_id, table_id)` 唯一。
- `(bk_tenant_id, dst_vm_table_id)` 唯一。
- `group_name` 不唯一，内部名称由可读片段加随机后缀生成。
- 所有 V4 子表冗余 `bk_tenant_id`，用于后续管理、审计和按租户清理。
- `RecordRuleV4Flow` 和 `RecordRuleV4Resolved` 一一对应；外部 `flow_name` 在 group 创建时生成并保持稳定。

输出 RT 固定补齐两个 `ResultTableOption`：

- `is_split_measurement=true`
- `enable_field_black_list=false`

## 模块设计

### 三层配置

V4 的核心是区分三种配置，避免后续排查时混成一团：

1. 用户输入配置：`RecordRuleV4Spec` + `RecordRuleV4SpecRecord`，记录用户提交的原始 group 配置。
2. 实时解析配置：`RecordRuleV4Resolved` + `RecordRuleV4ResolvedRecord`，记录当前路由、MetricQL、源 VMRT 范围。
3. 落地目标配置：`RecordRuleV4Flow`，保存基于 resolved 生成的单个 bkbase Flow 定义；执行过程只记录到 `RecordRuleV4Event`。

是否需要刷新计算任务只比较最新 resolved 语义结果，不比较最终生成的 `flow_config`。这样底层 Flow 模板、默认字段或 `operation_config` 规则变化时，不会把所有任务误判成可更新。

### Record Key

每条逻辑 record 都有内部稳定 `record_key`。

- JSON/API 模式可以显式传入 `record_key`，用于准确表达“修改这条记录”。
- 隐藏 key 的模式不应把 key 暴露给用户，后端先用 `input_config`，再用 `metric_name` 匹配上一份 spec record 并继承旧 `record_key`。
- `metric_name` 可以重复，因此 `metric_name` 只作为弱匹配兜底。
- `content_hash` 用完整 record 内容计算，用来判断同一个 `record_key` 的输入是否变化。

### 状态模型

`RecordRuleV4` 是声明式 API 的入口，bkbase Flow 是被 reconcile 的外部资源。

| 状态层 | 字段 | 含义 |
| --- | --- | --- |
| 声明状态 | `RecordRuleV4.desired_status` | 用户希望 group 处于 `running`、`stopped` 或 `deleted` |
| 解析状态 | `Resolved` condition | 当前 spec 是否成功解析为 resolved |
| 目标 Flow | `RecordRuleV4Spec.latest_resolved.flow` | 当前 spec 最近一次 resolved 生成的目标 Flow |
| 配置生效 | `RecordRuleV4.applied_resolved` | 哪个 resolved 已成功下发到外部 Flow |
| 启停生效 | `RecordRuleV4.applied_desired_status` | 最近一次成功下发的 running/stopped/deleted 状态 |
| 下发过程 | `flow_action.*` event | 本次 apply/delete 动作结果 |
| 实际状态 | `FlowHealthy` condition / `RecordRuleV4Flow.flow_status` | bkbase Flow 观测结果，简化为 `ok`、`abnormal`、`not_found` |
| 聚合状态 | `RecordRuleV4.status` | 给列表展示使用的状态，不作为唯一事实源 |
| 配置差异 | 前端计算 | 对比 `latest_resolved_id` 与 `applied_resolved_id`，不由后端落库或作为字段返回 |

典型状态差异：

- apply 接口失败：`applied_resolved` 仍指向最后一次成功配置；如果失败的是配置下发，前端可通过 `latest_resolved_id != applied_resolved_id` 判断仍有配置未生效，失败原因写入 `Reconciled` condition 和事件。
- 启停接口失败：`desired_status != applied_desired_status`，失败原因写入 `Reconciled` condition 和事件，但不会把 spec / resolved 推进到新版本。
- Flow 任务异常：配置已经成功下发，但 `FlowHealthy=false` 且 reason 为 `abnormal` 或 `not_found`。
- check 发现路由或 MetricQL 漂移：生成新的 resolved 和 latest flow；如果 `auto_refresh=false`，不自动 apply，前端按 latest/applied resolved 差异展示“可更新”。
- 删除失败：`desired_status=deleted` 但删除 Flow 失败，记录保持可见；只有 delete 成功后才设置 `deleted_at` 并聚合为 `status=deleted`。

### 核心方法

`metadata/models/record_rule/v4/models.py` 放模型、状态推导、名称生成、Flow 生成、事件校验：

```python
class RecordRuleV4(BaseModelWithTime):
    def use_spec(self, spec: RecordRuleV4Spec) -> None: ...
    def use_resolved(self, resolved: RecordRuleV4Resolved) -> None: ...
    def mark_flow_ready(self, flow: RecordRuleV4Flow) -> None: ...
    def mark_flow_applied(self, flow: RecordRuleV4Flow) -> None: ...
    def mark_desired_status_applied(self, desired_status: str) -> None: ...
    def mark_delete_applied(self) -> None: ...
    def sync_phase(self) -> None: ...
    def should_refresh(self, refresh_interval: int) -> bool: ...
```

`metadata/models/record_rule/v4/operator.py` 负责串联流程：

- `create`：创建 group、生成首个 spec、resolve、prepare flow，并按参数 apply。
- `update_spec`：处理用户配置、启停和删除。
- `manual_refresh`：用户主动检查，只 resolve + prepare flow，不自动下发。
- `reconcile`：后台任务入口，先 resolve，再按 `auto_refresh` 决定是否 apply。
- `apply`：下发 latest flow，或在 deleted 声明下删除 applied flow。
- `refresh_flow_health`：观测 applied flow 的实际状态。

具体职责拆分：

- `RecordRuleV4SpecBuilder`：创建 spec / spec record，并处理 `record_key` 继承。
- `RecordRuleV4Resolver`：调用 unify-query，将 spec 解析为 resolved。
- `RecordRuleV4Flow`：基于 resolved records 生成单个 bkbase Flow 配置。
- `RecordRuleV4Runner`：准备 latest flow，执行 apply/delete，观测 flow，并记录事件。

### Resource 门面

后续在 `metadata/resources/record_rule.py` 新增对外 Resource。Resource 只做参数校验、权限上下文整理和调用 operator，不直接拼 Flow 或调用 bkbase。

所有对外 Resource 统一要求携带：

- `bk_tenant_id`
- `bk_biz_id` / `space_uid` 二选一

返回值中也要补充 `bk_biz_id`、`space_uid`，便于上层继续做权限控制。

建议首期 Resource：

| Resource | 作用 |
| --- | --- |
| `CreateRecordRuleV4Resource` | 创建 V4 预计算 group |
| `ModifyRecordRuleV4Resource` | 修改 group 配置、records、启停 |
| `DeleteRecordRuleV4Resource` | 声明删除并触发 Flow 删除 |
| `GetRecordRuleV4Resource` | 查询单条 group 详情 |
| `ListRecordRuleV4Resource` | 按空间、状态、名称列表查询 |
| `RefreshRecordRuleV4Resource` | 手动触发 `manual_refresh`，只检查并标记可更新 |

### API 封装复用

`api/bkdata/default.py` 已有 V4 apply / delete 通用封装，V4 recording rule 不需要新增专用 bkdata API Resource：

- `ApplyDataLink` -> `POST /v4/apply/`
- `DeleteDataLink` -> `DELETE /v4/namespaces/{namespace}/{kind}/{name}/`

### 定时任务

在 `metadata/task/record_rule_v4.py` 放周期任务薄壳：

```python
def refresh_record_rule_v4():
    for rule in RecordRuleV4.objects.exclude(desired_status=RecordRuleV4DesiredStatus.DELETED.value):
        if rule.should_refresh():
            RecordRuleV4Operator(rule, source="scheduler").reconcile(auto_apply=rule.auto_refresh)
```

任务层不解析 check、不拼 Flow、不直接调用 bkbase，便于保持业务流程集中在 `RecordRuleV4Operator` 中维护。

## 生命周期

1. create
   - 生成 group 输出 `table_id` / `dst_vm_table_id` / `dst_vm_storage_name`，以及稳定外部 `flow_name`。
   - 创建输出 RT / ResultTableConfig / AccessVMRecord / ResultTableOption 后，推送 `SpaceTableIDRedis.push_space_table_ids` 和 `SpaceTableIDRedis.push_table_id_detail`。
   - 创建 `RecordRuleV4Spec` 和多条 `RecordRuleV4SpecRecord`。
   - 按 `metric_name` 补齐输出 `ResultTableField`；如果后续只是指标字段新增，只刷新 `SpaceTableIDRedis.push_table_id_detail`。
   - 逐条调用 unify-query check，生成 `RecordRuleV4Resolved` 和 `RecordRuleV4ResolvedRecord`。
   - 基于 resolved 生成唯一 `RecordRuleV4Flow`。
   - 可选立即 apply，成功后 `applied_resolved=current_spec.latest_resolved`，同时刷新 `applied_desired_status`。

2. update records
   - 创建新 spec 和新的 spec records。
   - 未传 `record_key` 的 record 尝试先按 `input_config`，再按 `metric_name` 继承旧 key。
   - 重新 resolve。
   - 如果 resolved 语义不变，不重新生成 Flow，也不因为 Flow 模板变化触发全量刷新。

3. stop/start
   - 只更新 `RecordRuleV4.desired_status`，不生成新的 spec / resolved / flow。
   - 不重新调用 unify-query。
   - 直接基于 `applied_resolved.flow` 下发新的 `desired_status`。
   - 成功后更新 `applied_desired_status`；失败时 `desired_status != applied_desired_status` 表示启停未生效。
   - Flow 计算内容指纹不包含运行态 `desired_status`，避免启停导致后续被误判为计算定义变化。

4. manual refresh
   - 对当前 spec 重新 check。
   - 如果 resolved 变化，写入 `current_spec.latest_resolved`，生成新 Flow；是否可更新由前端对比 latest/applied resolved。
   - 不自动下发。

5. reconcile
   - 周期任务会扫描非 deleted group。
   - resolve 无变化时只更新 `last_check_time`。
   - resolve 有变化且 `auto_refresh=true` 时自动 apply。
   - resolve 有变化且 `auto_refresh=false` 时只标记可更新。

6. delete
   - 将 desired status 置为 `deleted`。
   - 基于 group 稳定 `flow_name` 执行 delete。
   - Flow 删除成功后清空 `applied_resolved`，设置 `applied_desired_status=deleted`、`deleted_at` 并聚合为 `status=deleted`。

7. flow observe
   - 查询 `applied_resolved.flow` 对应的 bkbase Flow。
   - Flow 状态记录在 `RecordRuleV4Flow`，group 汇总到 `FlowHealthy` condition。
