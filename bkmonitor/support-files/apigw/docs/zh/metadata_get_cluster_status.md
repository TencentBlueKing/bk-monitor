### 功能描述

批量查询存储集群的实时健康状态。

- 支持 Elasticsearch、Doris、Kafka、VictoriaMetrics。
- Elasticsearch 和 Doris 返回物理磁盘容量及存储节点汇总；节点明细默认不返回，可通过参数按需获取。
- 不同类型的 `details` 使用各自固定的字段白名单，不会透传底层客户端或 SQL 的原始响应。
- 单个集群查询失败不会影响同批次的其他集群。

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|---|---|---|---|
| cluster_ids | list[int] | 是 | 存储集群 ID 列表，最多 20 个；重复 ID 按首次出现位置去重 |
| timeout | int | 否 | 单次底层网络操作的超时时间，单位秒，范围 1～30，默认 5 |
| include_node_details | bool | 否 | 是否返回 ES/Doris 节点明细，默认 false |

### 请求参数示例

```json
{
    "cluster_ids": [1, 2, 3],
    "timeout": 5,
    "include_node_details": false
}
```

默认响应中不包含 `details.node_details`。只有显式传入 `include_node_details=true` 时，ES/Doris 的 `details` 才包含该字段；公共 `nodes` 和 `capacity` 不受此参数影响。

接口最多使用 5 个工作线程，集群数超过 5 时会分批探测。`timeout` 作用于健康、容量、节点等单次底层网络操作，不是整批请求或单个集群的墙钟总超时；ES、Doris 需要顺序执行多个操作，因此请求总耗时还会受到集群数量、类型及网络状态影响。

### 公共响应结构

| 字段 | 类型 | 描述 |
|---|---|---|
| result | bool | 请求是否成功 |
| code | int | 返回码 |
| message | string | 返回信息 |
| data | list[dict] | 按请求顺序返回的集群状态列表 |

#### data[] 公共字段

| 字段 | 类型 | 描述 |
|---|---|---|
| cluster_id | int | 集群 ID |
| cluster_name | string/null | 集群名称；集群不存在时为 null |
| display_name | string/null | 集群显示名称 |
| cluster_type | string/null | `elasticsearch`、`doris`、`kafka`、`victoria_metrics` 或其他已注册类型 |
| status | string | `available`、`degraded`、`unavailable`、`unsupported` 或 `unknown` |
| is_connected | bool | 是否已连接到集群入口 |
| is_available | bool | 集群是否可提供服务；degraded 时仍为 true |
| nodes | object | 存储节点汇总，结构固定 |
| capacity | object | 物理磁盘容量汇总，结构固定，单位 bytes |
| details | object | 按 `cluster_type` 返回的固定特性字段，详见后续章节 |
| error | object/null | 主健康探测错误；附加指标采集错误位于 `details.collection_errors` |

#### nodes 公共字段

| 字段 | 类型 | 描述 |
|---|---|---|
| total | int/null | 存储节点总数；ES 为当前 data node 数，Doris 为非退役 BE 数 |
| available | int/null | 当前可用存储节点数；ES 与 total 一样表示当前已发现的 data node 数 |

Kafka、VictoriaMetrics、不支持的类型或未找到的集群无法提供节点汇总时，两个字段均为 null。

ES 无法从 cluster health 得知配置中“预期存在但当前未加入集群”的 data node，因此 `nodes.available` 不能用于判断相对预期拓扑是否有节点离线；ES 是否降级以 green/yellow/red 为准。

#### capacity 公共字段

| 字段 | 类型 | 描述 |
|---|---|---|
| total_bytes | int/null | 物理磁盘总容量 |
| used_bytes | int/null | 物理磁盘已使用容量，不等同于业务数据量 |
| available_bytes | int/null | 物理磁盘可用容量 |
| used_percent | float/null | `used_bytes / total_bytes * 100`，保留两位小数 |

ES 汇总当前 data node 的磁盘信息；Doris 汇总所有非退役 BE 的容量。Kafka、VictoriaMetrics 以及容量采集失败时，字段值为 null。

#### status 语义

| status | is_available | 说明 |
|---|---|---|
| available | true | 集群健康且可用 |
| degraded | true | 集群仍可用，但存在降级；例如 ES yellow、Doris 部分有效 BE 离线，或 Doris 已连接但无法查询 BE 状态 |
| unavailable | false | 集群不可用、连接失败、ES red 或 Doris 无可用有效 BE |
| unsupported | false | ClusterInfo 类型暂不支持运行时探测 |
| unknown | false | 请求的 cluster_id 在当前租户下不存在 |

### Elasticsearch 返回结构

#### details 字段

| 字段 | 类型 | 描述 |
|---|---|---|
| health_status | string/null | ES 原生健康状态：`green`、`yellow`、`red` |
| number_of_nodes | int/null | 当前加入集群的全部节点数量 |
| active_shards | int/null | active shard 数量 |
| initializing_shards | int/null | initializing shard 数量 |
| relocating_shards | int/null | relocating shard 数量 |
| unassigned_shards | int/null | unassigned shard 数量 |
| indices_store_bytes | int/null | data node 上 `disk.indices` 的汇总值，即索引数据占用；与公共 capacity 的物理磁盘占用口径不同 |
| node_details | list[object] | data node 明细，固定结构；仅 `include_node_details=true` 时返回 |
| collection_errors | list[object] | 容量或节点角色附加查询错误；无错误时为空数组 |

#### details.node_details[] 字段

| 字段 | 类型 | 描述 |
|---|---|---|
| name | string/null | 节点名称 |
| host | string/null | 节点 host |
| ip | string/null | 节点 IP |
| roles | list[string] | 通过 `_cat/nodes` 获取的节点角色；不同 ES 版本可能返回角色名或角色缩写，统一转换为字符串数组 |
| shard_count | int/null | 分配到该节点的 shard 数量 |
| capacity | object | 节点物理磁盘容量，字段与公共 capacity 完全相同 |
| indices_store_bytes | int/null | 该节点 `disk.indices` 的字节数 |

`_cat/allocation` 中没有磁盘容量的 UNASSIGNED 汇总行不会进入 `node_details`。节点角色来自 `_cat/nodes`，优先按节点名与 allocation 关联，名称缺失时按 IP 关联；角色查询失败时返回空数组，并写入 `collection_errors`。

#### Elasticsearch 示例（include_node_details=true）

```json
{
    "cluster_id": 1,
    "cluster_name": "es-default",
    "display_name": "默认 ES",
    "cluster_type": "elasticsearch",
    "status": "degraded",
    "is_connected": true,
    "is_available": true,
    "nodes": {"total": 2, "available": 2},
    "capacity": {
        "total_bytes": 322122547200,
        "used_bytes": 107374182400,
        "available_bytes": 214748364800,
        "used_percent": 33.33
    },
    "details": {
        "health_status": "yellow",
        "number_of_nodes": 3,
        "active_shards": 120,
        "initializing_shards": 0,
        "relocating_shards": 0,
        "unassigned_shards": 2,
        "indices_store_bytes": 96636764160,
        "node_details": [
            {
                "name": "es-data-1",
                "host": "127.0.0.1",
                "ip": "127.0.0.1",
                "roles": ["d"],
                "shard_count": 60,
                "capacity": {
                    "total_bytes": 161061273600,
                    "used_bytes": 53687091200,
                    "available_bytes": 107374182400,
                    "used_percent": 33.33
                },
                "indices_store_bytes": 48318382080
            }
        ],
        "collection_errors": []
    },
    "error": null
}
```

### Doris 返回结构

#### details 字段

| 字段 | 类型 | 描述 |
|---|---|---|
| data_used_bytes | int/null | 所有非退役 BE 的业务数据占用汇总 |
| trash_used_bytes | int/null | 所有非退役 BE 的回收站占用汇总 |
| remote_used_bytes | int/null | 所有非退役 BE 的远端存储占用汇总；旧版本不支持时为 null |
| tablet_count | int/null | 所有非退役 BE 的 tablet 数量汇总 |
| max_disk_used_percent | float/null | 所有非退役 BE 的最大单盘使用率 |
| node_details | list[object] | SHOW BACKENDS 节点明细的固定投影；仅 `include_node_details=true` 时返回 |
| collection_errors | list[object] | SHOW BACKENDS 查询错误；无错误时为空数组。查询失败时无法确认 BE 状态，集群返回 degraded |

#### details.node_details[] 字段

| 字段 | 类型 | 描述 |
|---|---|---|
| backend_id | int/null | BE 节点 ID |
| host | string/null | BE 节点 host |
| alive | bool | BE 是否存活 |
| decommissioned | bool | BE 是否处于退役状态 |
| tablet_count | int/null | BE 上的 tablet 数量 |
| capacity | object | 节点物理磁盘容量，字段与公共 capacity 完全相同 |
| data_used_bytes | int/null | BE 业务数据占用 |
| trash_used_bytes | int/null | BE 回收站占用 |
| remote_used_bytes | int/null | BE 远端存储占用，旧版本不支持时为 null |
| max_disk_used_percent | float/null | BE 的最大单盘使用率 |
| last_heartbeat | string/null | 最近心跳时间 |
| error_message | string | BE 错误信息，无错误时为空字符串 |
| version | string/null | Doris BE 版本 |
| node_role | string/null | BE 节点角色，旧版本不支持时为 null |

退役节点会保留在 `node_details` 便于诊断，但不计入公共 `nodes` 和 `capacity` 汇总。

#### Doris 示例（include_node_details=true）

```json
{
    "cluster_id": 2,
    "cluster_name": "doris-default",
    "display_name": "默认 Doris",
    "cluster_type": "doris",
    "status": "degraded",
    "is_connected": true,
    "is_available": true,
    "nodes": {"total": 2, "available": 1},
    "capacity": {
        "total_bytes": 8589934592,
        "used_bytes": 3221225472,
        "available_bytes": 5368709120,
        "used_percent": 37.5
    },
    "details": {
        "data_used_bytes": 2147483648,
        "trash_used_bytes": 134217728,
        "remote_used_bytes": 268435456,
        "tablet_count": 30,
        "max_disk_used_percent": 60.0,
        "node_details": [
            {
                "backend_id": 10001,
                "host": "127.0.0.1",
                "alive": true,
                "decommissioned": false,
                "tablet_count": 10,
                "capacity": {
                    "total_bytes": 4294967296,
                    "used_bytes": 1073741824,
                    "available_bytes": 3221225472,
                    "used_percent": 25.0
                },
                "data_used_bytes": 1073741824,
                "trash_used_bytes": 134217728,
                "remote_used_bytes": 268435456,
                "max_disk_used_percent": 30.0,
                "last_heartbeat": "2026-08-03 10:00:00",
                "error_message": "",
                "version": "2.1.7",
                "node_role": "mix"
            }
        ],
        "collection_errors": []
    },
    "error": null
}
```

### Kafka 返回结构

Kafka 不返回节点明细和物理容量，公共 `nodes`、`capacity` 中的值均为 null。

#### details 字段

| 字段 | 类型 | 描述 |
|---|---|---|
| bootstrap_servers | string/null | 实际探测使用的 bootstrap servers |
| broker_count | int/null | broker 数量 |
| topic_count | int/null | topic 数量 |
| security_protocol | string/null | `PLAINTEXT`、`SSL`、`SASL_PLAINTEXT` 或 `SASL_SSL` |
| sasl_mechanisms | string/null | SASL 机制；未启用 SASL 时为 null |
| auth_enabled | bool/null | 是否启用认证 |
| collection_errors | list[object] | 保留的统一附加采集错误字段，当前正常情况下为空数组 |

```json
{
    "bootstrap_servers": "kafka.example.com:9092",
    "broker_count": 3,
    "topic_count": 120,
    "security_protocol": "SASL_SSL",
    "sasl_mechanisms": "SCRAM-SHA-512",
    "auth_enabled": true,
    "collection_errors": []
}
```

### VictoriaMetrics 返回结构

VictoriaMetrics 不返回节点明细和物理容量，公共 `nodes`、`capacity` 中的值均为 null。

#### details 字段

| 字段 | 类型 | 描述 |
|---|---|---|
| url | string/null | 实际访问的 health URL |
| status_code | int/null | health HTTP 状态码 |
| response | string/null | HTTP 状态异常时最多返回前 200 个字符；成功时为 null |
| collection_errors | list[object] | 保留的统一附加采集错误字段，当前正常情况下为空数组 |

```json
{
    "url": "http://vm.example.com:8428/health",
    "status_code": 200,
    "response": null,
    "collection_errors": []
}
```

### collection_errors 字段

健康入口已连接、但容量或节点等后续查询失败时，错误写入固定结构的 `details.collection_errors[]`。ES allocation/nodes 失败不覆盖 cluster health 状态；Doris `SHOW BACKENDS` 同时用于判断 BE 健康，失败时集群状态降为 degraded。

| 字段 | 类型 | 描述 |
|---|---|---|
| component | string/null | `capacity`、`node_details` 或 `backends` |
| code | string/null | `ES_ALLOCATION_QUERY_FAILED`、`ES_NODES_QUERY_FAILED` 或 `DORIS_BACKENDS_QUERY_FAILED` |
| message | string/null | 错误摘要 |
| details.type | string/null | 异常类型 |
| details.message | string/null | 异常消息 |

### 顶层 error 字段

| 字段 | 类型 | 描述 |
|---|---|---|
| code | string | 错误码 |
| message | string | 错误摘要 |
| details | object | 固定错误上下文，不包含集群凭据 |

可能的错误码包括：

- `CLUSTER_NOT_FOUND`
- `CONNECTION_FAILED`
- `CLUSTER_UNHEALTHY`
- `HTTP_UNHEALTHY`
- `INVALID_CONFIG`
- `UNSUPPORTED_CLUSTER_TYPE`
- `STATUS_COLLECTION_FAILED`

### 不支持类型和不存在集群

- 已注册但不支持探测的类型：返回 `status=unsupported`，`details={}`。
- 当前租户下不存在的 ID：返回 `status=unknown`，仅 `cluster_id` 有值，其他身份字段为 null，`error.code=CLUSTER_NOT_FOUND`。

### 版本兼容规则

接口只输出上述固定字段，不直接透传 Elasticsearch CAT API 或 Doris SHOW BACKENDS 的原始行。节点明细还需显式设置 `include_node_details=true` 才会进入响应。

#### Elasticsearch

| 标准字段 | 兼容读取的底层字段 |
|---|---|
| name | `node`、`name` |
| roles | `_cat/nodes` 的 `node.role`、`role`、`roles`、`nodeRole` |
| shard_count | `shards`、`shardCount` |
| capacity.total_bytes | `disk.total`、`diskTotal` |
| capacity.used_bytes | `disk.used`、`diskUsed`；缺失时使用 total - available |
| capacity.available_bytes | `disk.avail`、`diskAvail` |
| capacity.used_percent | `disk.percent`、`diskPercent`；集群汇总始终重新计算 |
| indices_store_bytes | `disk.indices`、`diskIndices` |

- 数字字符串统一转换为 int/float。
- roles 无论底层返回字符串、逗号分隔字符串还是数组，统一转换为 `list[string]`；无角色标记 `-` 统一转换为空数组。
- 版本不提供的可选字段返回 null 或空数组，不新增动态字段。

#### Doris

| 标准字段 | 兼容读取的 SHOW BACKENDS 字段 |
|---|---|
| decommissioned | `SystemDecommissioned`、`IsDecommissioned` |
| trash_used_bytes | `TrashUsedCapacity`、旧版本拼写 `TrashUsedCapcacity` |
| error_message | `ErrMsg`、`ErrorMessage` |
| remote_used_bytes | `RemoteUsedCapacity`，旧版本缺失时为 null |
| node_role | `NodeRole`，旧版本缺失时为 null |

- B/KB/MB/GB/TB/PB/EB 统一按 1024 进制转换为 bytes。
- Alive、退役状态兼容 bool、数字和字符串形式，统一转换为 bool。
- SHOW BACKENDS 新增的其他列不会自动出现在接口响应中；需要明确评审并加入固定结构后才会对外暴露。
