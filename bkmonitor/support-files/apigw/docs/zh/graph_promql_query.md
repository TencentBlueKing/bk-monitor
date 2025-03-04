### 功能描述

通过PromQL查询图表数据


#### 接口参数

| 字段               | 类型  | 必选 | 描述       |
|------------------|-----|----|----------|
| bk_biz_id        | int | 是  | 业务ID     |
| promql           | str | 否  | PromQL语句 |
| start_time       | int | 是  | 开始时间     |
| end_time         | int | 是  | 结束时间     |
| step             | str | 否  | 采样步长     |
| format           | str | 否  | 输出格式     |
| type             | str | 否  | 查询类型     |
| down_sample_range | str | 否  | 降采样周期    |

#### 请求示例

```json
{
  "down_sample_range": "20s",
  "end_time": 1740032795,
  "format": "time_series",
  "promql": "avg(avg_over_time(bkmonitor:system:disk:in_use[1m]))",
  "start_time": 1740011195,
  "step": "auto",
  "type": "range",
  "bk_biz_id": "2"
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 结果     |

#### data 字段说明

| 字段      | 类型         | 描述       |
|---------|------------|----------|
| series  | list[dict] | 时序数据样本信息 |
| metrics | list[dict] | 指标信息     |

#### data.series 时序数据样本信息

| 字段           | 类型   | 描述              |
|:-------------|:-----|:----------------|
| dimensions   | dict | 时间序列的维度信息       |
| target       | str  | 查询的目标表达式        |
| metric_field | str  | 指标字段名称          |
| datapoints   | list | 时间序列数据点，包含值和时间戳 |
| alias        | str  | 指标的别名           |
| unit         | str  | 指标的单位           |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "metrics": [],
    "series": [
      {
        "alias": "_result_",
        "metric_field": "_result_",
        "unit": "",
        "target": "",
        "dimensions": {},
        "datapoints": [
          [
            35.68620465787336,
            1740011940000
          ],
          [
            35.67780711755964,
            1740012000000
          ],
          [
            35.68838979188922,
            1740012060000
          ],
          [
            35.68447011790601,
            1740012120000
          ]
        ]
      }
    ]
  }
}
```
