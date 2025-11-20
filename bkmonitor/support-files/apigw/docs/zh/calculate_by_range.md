### 功能描述

按时间范围计算指标数据，支持多时间点对比分析、分组聚合、增长率和占比计算。适用于 APM 场景的指标统计和对比分析。

### 请求参数

| 字段                | 类型           | 必选 | 描述                                                                                                                                                                                     |
|-------------------|--------------|----|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| bk_biz_id         | int          | 是  | 业务 ID                                                                                                                                                                                  |
| app_name          | string       | 是  | 应用名称                                                                                                                                                                                   |
| metric_group_name | string       | 是  | 指标组，可选 `trpc`、`resource`                                                                                                                                                               |
| metric_cal_type   | string       | 是  | 指标计算类型，可选 `request_total`（请求量）、`success_rate`（成功率）、`timeout_rate`（超时率）、`exception_rate`（异常率）、`avg_duration`（平均耗时）、`p50_duration`（P50 耗时）、`p95_duration`（P95 耗时）、`p99_duration`（P99 耗时） |
| start_time        | int          | 否  | 开始时间（Unix 时间戳，秒）                                                                                                                                                                       |
| end_time          | int          | 否  | 结束时间（Unix 时间戳，秒）                                                                                                                                                                       |
| baseline          | string       | 否  | 对比基准时间偏移，默认 `0s`，表示当前时间                                                                                                                                                                |
| time_shifts       | List[string] | 否  | 时间偏移列表，支持 `1d`（1 天前）、`1w`（1 周前）等，最多支持 2 个对比时间点                                                                                                                                         |
| filter_dict       | dict         | 否  | 过滤条件字典                                                                                                                                                                                 |
| where             | List[dict]   | 否  | 过滤条件列表，与 `filter_dict` 合并生效                                                                                                                                                            |
| group_by          | List[string] | 否  | 分组字段列表，用于维度聚合                                                                                                                                                                          |
| options           | dict         | 否  | 额外配置选项                                                                                                                                                                                 |

#### 时间偏移格式说明

时间偏移支持以下格式：

- `0s`：当前时间（默认）
- `1h`：1 小时前
- `1d`：1 天前
- `1w`：1 周前
- `1M`：1 月前

#### options 配置说明

options 为可选配置，支持以下字段：

| 字段   | 类型   | 必选 | 描述        |
|------|------|----|-----------|
| trpc | dict | 否  | tRPC 相关配置 |

**options.trpc 字段说明**

| 字段          | 类型     | 必选 | 描述   | 枚举值                          |
|-------------|--------|----|------|------------------------------|
| kind        | string | 是  | 调用类型 | `caller`（主调）、`callee`（被调）    |
| temporality | string | 是  | 时间性  | `cumulative`（累加）、`delta`（差值） |

#### 过滤条件（where）

`where` 字段是一个列表，每个元素包含以下字段：

| 字段        | 类型     | 必选 | 描述                  |
|-----------|--------|----|---------------------|
| key       | string | 是  | 字段名                 |
| value     | List   | 是  | 可取值的列表              |
| method    | string | 否  | 匹配方式，默认 `eq`        |
| condition | string | 否  | 条件连接符，可选 `and`、`or` |

**method 枚举值说明**

| 枚举值       | 含义   |
|-----------|------|
| `eq`      | 等于   |
| `neq`     | 不等于  |
| `include` | 包含   |
| `exclude` | 不包含  |
| `reg`     | 正则匹配 |

### 支持的聚合与过滤字段（where.key / group_by）

`where.key` 和 `group_by` 支持的字段取决于 `options.trpc.kind`。

#### 1. 通用字段

| 字段名 (key)          | 描述                      | Trace 映射字段                     |
|:-------------------|:------------------------|:-------------------------------|
| `service_name`     | 【重要】服务名，按服务过滤时，必须使用此字段。 | resource.service.name          |
| `namespace`        | 物理环境                    | attributes.trpc.namespace      |
| `env_name`         | 用户环境                    | attributes.trpc.envname        |
| `caller_service`   | 主调 Service              | attributes.trpc.caller_service |
| `caller_method`    | 主调接口                    | attributes.trpc.caller_method  |
| `callee_service`   | 被调 Service              | attributes.trpc.callee_service |
| `callee_method`    | 被调接口                    | attributes.trpc.callee_method  |
| `code`             | 返回码                     | attributes.trpc.status_code    |
| `version`          | 版本                      | -                              |
| `region`           | 地域                      | -                              |
| `canary`           | 金丝雀                     | -                              |
| `user_ext1`        | 预留字段1                   | -                              |
| `user_ext2`        | 预留字段2                   | -                              |
| `user_ext3`        | 预留字段3                   | -                              |
| `caller_con_setid` | 主调 SetID                | -                              |
| `callee_con_setid` | 被调 SetID                | -                              |
| `caller_group`     | 主调流量组                   | -                              |

#### 2. 模式差异字段

| 字段名 (key)        | 主调模式 (kind=caller) | 被调模式 (kind=callee) | Trace 映射字段 (主调 \| 被调)  |
|:-----------------|:-------------------|:-------------------|:-----------------------|
| `instance`       | 主调 IP              | 被调 IP              | attributes.net.host.ip |
| `container_name` | 主调容器               | 被调容器               | -                      |
| `caller_server`  | -                  | 主调服务               | -                      |
| `callee_server`  | 被调服务               | -                  | -                      |

#### 3. 模式特有字段

| 字段名 (key)          | 适用模式         | 描述    | Trace 映射字段             |
|:-------------------|:-------------|:------|:-----------------------|
| `callee_ip`        | 仅主调 (caller) | 被调 IP | attributes.net.peer.ip |
| `callee_container` | 仅主调 (caller) | 被调容器  | -                      |
| `caller_ip`        | 仅被调 (callee) | 主调 IP | attributes.net.peer.ip |
| `caller_container` | 仅被调 (callee) | 主调容器  | -                      |


#### 4. 查询关联调用链

上文已给出了各字段与 Trace 映射字段的对应关系，您可以使用映射字段及接口返回的字段值，在调用链查询接口中进行关联查询。

值得注意的是，请为 `options.trpc.kind` 构造查询条件，以确保检索到正确的调用链数据：
* `caller`：增加 `kind=[3, 4]` 表示仅过滤出「主调」及「异步主调」的数据。
* `callee`：增加 `kind=[1, 2]` 表示仅过滤出「被调」及「异步被调」的数据。

### 请求参数示例

```json
{
    "app_name": "trpc-cluster-access-demo",
    "metric_group_name": "trpc",
    "metric_cal_type": "request_total",
    "baseline": "0s",
    "where": [
        {
            "method": "eq",
            "value": [
                "example.greeter"
            ],
            "condition": "and",
            "key": "service_name"
        },
        {
            "method": "eq",
            "value": [
                "SayHi"
            ],
            "condition": "and",
            "key": "callee_method"
        }
    ],
    "group_by": [
        "callee_method"
    ],
    "time_shifts": [
        "0s",
        "1d"
    ],
    "options": {
        "trpc": {
            "kind": "caller",
            "temporality": "cumulative"
        }
    },
    "start_time": 1763535864,
    "end_time": 1763539464,
    "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 计算结果数据 |

#### data 字段说明

| 字段    | 类型           | 描述     |
|-------|--------------|--------|
| total | int          | 数据总条数  |
| data  | List[Record] | 具体数据列表 |

#### data.data 字段说明

| 字段           | 类型     | 描述                                                  |
|--------------|--------|-----------------------------------------------------|
| dimensions   | dict   | 维度信息，键为 `group_by` 指定的字段                            |
| {time_shift} | number | 各时间偏移点的指标值，键为 `time_shifts` 中的值                     |
| growth_rates | dict   | 相对于 `baseline` 的增长率（百分比），键为 `time_shifts` 中的值       |
| proportions  | dict   | 占比（百分比），仅 `request_total` 类型返回，键为 `time_shifts` 中的值 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 1,
        "data": [
            {
                "dimensions": {
                    "callee_method": "SayHi"
                },
                "0s": 21907,
                "1d": 21896,
                "growth_rates": {
                    "0s": -0.0,
                    "1d": 0.05
                },
                "proportions": {
                    "0s": 100.0,
                    "1d": 100.0
                }
            }
        ]
    }
}
```

### 使用说明

1. **指标类型**：根据 `metric_cal_type` 选择不同的计算方式：
   - `request_total`：统计请求总量，返回整数值
   - `success_rate`、`timeout_rate`、`exception_rate`：统计比率，返回百分比（0-100）
   - `avg_duration`、`p50_duration`、`p95_duration`、`p99_duration`：统计耗时，返回浮点数

2. **时间对比**：通过 `time_shifts` 可实现同环比分析，最多支持 2 个对比时间点。`baseline` 指定增长率计算的基准时间。

3. **增长率计算规则**：
   - 当基准值和对比值均为 0 时，增长率为 0%
   - 当基准值为 0、对比值不为 0 时，增长率为 100%
   - 当基准值不为 0、对比值为 0 时，增长率为 -100%
   - 其他情况：增长率 = (基准值 - 对比值) / 对比值 × 100%

4. **占比计算**：仅当 `metric_cal_type` 为 `request_total` 时返回 `proportions` 字段，表示各维度值占总量的百分比。

5. **维度聚合**：通过 `group_by` 可指定分组字段，返回结果会按这些维度进行聚合统计。

6. **数据排序**：返回的数据列表已按维度排序，如果包含 `time` 字段，则按时间倒序排列。

7. **性能优化**：该接口支持预计算优化，在特定配置下会自动路由到预计算指标，提升查询性能。
