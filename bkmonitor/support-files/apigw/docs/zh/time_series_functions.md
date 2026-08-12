### 功能描述

获取统一查询模块可用的计算函数列表，按分类返回函数元数据（名称、说明、参数等），供时序查询配置时选择计算函数。


### 请求参数

| 字段 | 类型   | 必选 | 描述 |
|------|--------|------|------|
| type | string | 否   | 函数范围。为空时仅返回基础计算函数；传 `grafana` 时额外包含 Grafana 专用函数（如 `top` / `bottom`） |

### 请求参数示例

```
GET /app/data_query/time_series_functions/?type=grafana
```

不传 `type`（仅基础函数）：

```
GET /app/data_query/time_series_functions/
```

### 响应参数

| 字段      | 类型   | 描述       |
|-----------|--------|------------|
| result    | bool   | 请求是否成功 |
| code      | int    | 返回的状态码 |
| message   | str    | 描述信息   |
| data      | list   | 按分类分组的函数列表 |

#### data 元素字段说明

| 字段        | 类型         | 描述     |
|-------------|--------------|----------|
| id          | string       | 分类 ID，可选值：`change`（指标变化）、`arithmetic`（数学计算）、`sort`（排序）、`time_shift`（时间偏移） |
| name        | string       | 分类名称 |
| description | string       | 分类说明 |
| children    | list[object] | 该分类下的函数列表 |

#### data.children 元素字段说明

| 字段                | 类型         | 描述 |
|---------------------|--------------|------|
| id                  | string       | 函数 ID（如 `rate`、`increase`、`abs`） |
| name                | string       | 函数名称 |
| description         | string       | 函数说明 |
| params              | list[object] | 函数参数定义 |
| position            | int          | 参数插入位置，默认 `0` |
| time_aggregation    | bool         | 是否为时间聚合函数 |
| with_dimensions     | bool         | 是否携带维度 |
| support_expression  | bool         | 是否支持表达式 |
| category            | string       | 所属分类 ID |
| ignore_unit         | bool         | 是否忽略单位 |

#### data.children.params 元素字段说明

| 字段        | 类型         | 描述 |
|-------------|--------------|------|
| id          | string       | 参数 ID |
| name        | string       | 参数名称 |
| description | string       | 参数说明 |
| type        | string       | 参数类型，如 `string`、`int` |
| default     | any          | 默认值 |
| shortlist   | list         | 可选值列表 |
| required    | bool         | 是否必填，默认 `true` |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": "change",
      "name": "指标变化",
      "description": "计算指标变化的相关函数",
      "children": [
        {
          "id": "rate",
          "name": "rate",
          "description": "每秒平均增长率（仅支持单调增长指标，遇到下降会从0开始计算）",
          "params": [
            {
              "id": "window",
              "name": "window",
              "description": "时间窗口",
              "type": "string",
              "default": "2m",
              "shortlist": ["1m", "2m", "5m", "10m", "20m"],
              "required": true
            }
          ],
          "position": 0,
          "time_aggregation": true,
          "with_dimensions": false,
          "support_expression": false,
          "category": "change",
          "ignore_unit": false
        }
      ]
    },
    {
      "id": "sort",
      "name": "排序",
      "description": "排序函数",
      "children": [
        {
          "id": "top",
          "name": "top",
          "description": "最大的N个维度，不可用于多指标计算",
          "params": [
            {
              "id": "n",
              "name": "n",
              "description": "维度数量",
              "type": "int",
              "default": "5",
              "shortlist": ["3", "5", "10", "20"],
              "required": true
            }
          ],
          "position": 0,
          "time_aggregation": false,
          "with_dimensions": false,
          "support_expression": false,
          "category": "sort",
          "ignore_unit": false
        }
      ]
    }
  ]
}
```
