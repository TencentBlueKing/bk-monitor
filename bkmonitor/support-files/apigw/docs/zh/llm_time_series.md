### 功能描述

查询 Agent LLM 指标时序数据。当前接口处于前端联调 mock 阶段，会根据请求时间范围生成稳定的模拟数据；后续会替换为基于真实 Trace/Span 的查询结果。

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

当前支持的 `cal_type`：

| cal_type | 描述 |
|---|---|
| input_tokens | 输入 Token 数 |
| output_tokens | 输出 Token 数 |
| total_tokens | Token 总数 |
| cache_tokens | 缓存 Token 数 |
| request_count | 请求数 / 提问数 |
| model_call_count | 模型调用次数 |
| duration | 模型调用耗时，单位为微秒（μs） |
| operation_count | 操作次数 |

当前支持的 `group_by`：

| group_by | 描述 |
|---|---|
| `[]` | 不分组 |
| `["gen_ai.response.model"]` | 按模型分组 |
| `["gen_ai.operation.name"]` | 按操作类型分组 |

### 页面数据请求示例

原型图中的输入、输出 Token 趋势需要分别请求，再由前端绘制到同一张图中。

#### 输入 Token 趋势

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "input_tokens",
    "group_by": []
}
```

#### 输出 Token 趋势

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "output_tokens",
    "group_by": []
}
```

#### 模型调用次数趋势

```json
{
    "bk_biz_id": 11,
    "app_name": "sand_local_dev",
    "service_name": "sand_local_dev",
    "start_time": 1788364800,
    "end_time": 1788368400,
    "cal_type": "model_call_count",
    "group_by": []
}
```

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
| series | list | 时序曲线列表 |
| mock | bool | 是否为 mock 数据；当前固定为 `true` |

#### series 元素

| 字段名 | 类型 | 描述 |
|---|---|---|
| datapoints | list | 时序点列表，每个点格式为 `[value, timestamp_ms]`；`duration` 的 value 单位为微秒（μs） |
| target | string | 分组名称；仅分组查询时返回 |
| dimensions | object | 分组维度；仅分组查询时返回 |

### 响应参数示例

不分组：

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "series": [
            {
                "datapoints": [
                    [2600, 1788364800000],
                    [3337, 1788365100000],
                    [3978, 1788365400000]
                ]
            }
        ],
        "mock": true
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
        "series": [
            {
                "datapoints": [
                    [820000, 1788364800000],
                    [969293, 1788365100000],
                    [1100800, 1788365400000]
                ],
                "target": "hunyuan-turbo",
                "dimensions": {
                    "gen_ai.response.model": "hunyuan-turbo"
                }
            },
            {
                "datapoints": [
                    [1043399, 1788364800000],
                    [1185310, 1788365100000],
                    [1305908, 1788365400000]
                ],
                "target": "deepseek-r1",
                "dimensions": {
                    "gen_ai.response.model": "deepseek-r1"
                }
            },
            {
                "datapoints": [
                    [1260497, 1788364800000],
                    [1391579, 1788365100000],
                    [1503535, 1788365400000]
                ],
                "target": "qwen3-32b",
                "dimensions": {
                    "gen_ai.response.model": "qwen3-32b"
                }
            }
        ],
        "mock": true
    }
}
```

### 使用说明

1. 当前接口用于 LLM 概览页趋势图联调，数据为 mock。
2. 点数会根据查询时间范围自动控制，每条曲线最多返回 60 个点，时间戳单位为毫秒。
3. 当前只支持单字段聚合，不支持同时按多个字段分组。
