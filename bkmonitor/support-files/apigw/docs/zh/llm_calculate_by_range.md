### 功能描述

查询 Agent LLM 指标在指定时间范围内的聚合值。当前接口处于前端联调 mock 阶段，会根据请求时间范围生成稳定的模拟数据；后续会替换为基于真实 Trace/Span 的查询结果。

该接口适用于指标卡片、饼图和排行图，不返回时序点。

### 请求参数

| 字段名 | 类型 | 必选 | 描述 |
|---|---|---|---|
| bk_biz_id | int | 是 | 业务 ID |
| app_name | string | 是 | APM 应用名称 |
| service_name | string | 否 | OTel 服务名称；当前 mock 阶段不影响返回结果 |
| start_time | int | 是 | 查询开始时间，Unix 时间戳，单位为秒 |
| end_time | int | 是 | 查询结束时间，Unix 时间戳，单位为秒，必须大于 `start_time` |
| cal_type | string | 是 | 指标类型，见下方支持范围 |
| group_by | list | 否 | 聚合字段，默认 `[]` |
| baseline | string | 否 | 增长率计算基准，默认 `0s`，必须包含在 `time_shifts` 中 |
| time_shifts | list | 否 | 时间偏移，例如 `["0s", "1d"]`；自动补入 `0s`，最多支持两个对比时段 |

当前支持的 `cal_type`：

| cal_type | 描述 |
|---|---|
| input_tokens | 输入 Token 数 |
| output_tokens | 输出 Token 数 |
| total_tokens | Token 总数 |
| cache_tokens | 缓存 Token 数 |
| request_count | 请求数 / 提问数 |
| model_call_count | 模型调用次数 |
| duration | 模型调用平均耗时，单位为微秒（μs） |
| operation_count | 操作次数 |

当前支持的 `group_by`：

| group_by | 描述 |
|---|---|
| `[]` | 不分组 |
| `["gen_ai.response.model"]` | 按模型分组 |
| `["gen_ai.operation.name"]` | 按操作类型分组 |

### 页面数据请求示例

#### 概览指标卡

**输入 Token 总数**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "input_tokens",
    "group_by": [],
    "baseline": "0s",
    "time_shifts": ["0s", "1d"]
}
```

对应响应中的 `data`：

```json
{
    "total": 1,
    "data": [
        {
            "dimensions": {},
            "0s": 72130,
            "1d": 69220,
            "growth_rates": {
                "0s": 0,
                "1d": 4.2
            }
        }
    ]
}
```

前端读取 `0s` 展示当前值，读取 `growth_rates["1d"]` 展示 `+4.2%`。

**输出 Token 总数**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "output_tokens",
    "group_by": [],
    "baseline": "0s",
    "time_shifts": ["0s", "1d"]
}
```

**Token 总数**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "total_tokens",
    "group_by": [],
    "baseline": "0s",
    "time_shifts": ["0s", "1d"]
}
```

**缓存 Token 总数**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "cache_tokens",
    "group_by": [],
    "baseline": "0s",
    "time_shifts": ["0s", "1d"]
}
```

**请求数（提问数）**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "request_count",
    "group_by": [],
    "baseline": "0s",
    "time_shifts": ["0s", "1d"]
}
```

**模型调用次数**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "model_call_count",
    "group_by": [],
    "baseline": "0s",
    "time_shifts": ["0s", "1d"]
}
```

指标卡通过一次请求同时获得当前值、对比时段值和增长率。前端读取 `0s` 展示当前值，读取 `growth_rates["1d"]` 展示与前一天相同时间范围相比的增长率，例如 `+4.2%`；其他指标卡只需替换 `cal_type`。

#### 分布和排行

**操作类型分布**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "operation_count",
    "group_by": ["gen_ai.operation.name"]
}
```

**模型调用总数排行**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "model_call_count",
    "group_by": ["gen_ai.response.model"]
}
```

**模型调用平均耗时 TOP10**

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "duration",
    "group_by": ["gen_ai.response.model"]
}
```

当前 mock 返回 3 个模型。前端按 `0s` 的值倒序排列，并最多展示 10 条。

### 响应参数

| 字段名 | 类型 | 描述 |
|---|---|---|
| result | bool | 请求是否成功 |
| code | int | 返回状态码 |
| message | string | 返回信息 |
| data | object | 查询结果 |

#### data 字段

| 字段名 | 类型 | 描述 |
|---|---|---|
| total | int | 返回记录数量 |
| data | list | 聚合结果列表 |

#### data.data 元素

| 字段名 | 类型 | 描述 |
|---|---|---|
| dimensions | object | 分组维度；不分组时为空对象 |
| 0s | number | 当前时间范围内的聚合值；`duration` 的值单位为微秒（μs） |
| 时间偏移字段 | number | 对应偏移时间范围内的聚合值，字段名来自 `time_shifts`，例如 `1d` |
| growth_rates | object | 各时间偏移相对 `baseline` 的增长率；无可计算值时为 `null` |

### 响应参数示例

不分组：

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 1,
        "data": [
            {
                "dimensions": {},
                "0s": 72130,
                "1d": 69220,
                "growth_rates": {
                    "0s": 0,
                    "1d": 4.2
                }
            }
        ]
    }
}
```

按模型分组：

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 3,
        "data": [
            {
                "dimensions": {
                    "gen_ai.response.model": "hunyuan-turbo"
                },
                "0s": 947000,
                "growth_rates": {
                    "0s": 0
                }
            },
            {
                "dimensions": {
                    "gen_ai.response.model": "deepseek-r1"
                },
                "0s": 1177000,
                "growth_rates": {
                    "0s": 0
                }
            },
            {
                "dimensions": {
                    "gen_ai.response.model": "qwen3-32b"
                },
                "0s": 1407000,
                "growth_rates": {
                    "0s": 0
                }
            }
        ]
    }
}
```

### 使用说明

1. 当前接口用于 LLM 概览页指标卡片、饼图和排行图联调，数据为 mock。
2. 返回结构对齐 APM 通用 `calculate_by_range`，`0s` 表示当前时间范围的聚合值。
3. 当前返回 `time_shifts` 对应的聚合值和 `growth_rates`，暂不返回 `proportions`。
4. 当前只支持单字段聚合，不支持同时按多个字段分组。
