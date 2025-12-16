### 功能描述

批量创建或更新自定义时序指标
- 如果指标中提供了 field_id，则更新对应的指标
- 如果未提供 field_id，则创建新指标（此时 field_name 为必填项）

**重要说明：更新操作为全量更新**
- 更新 `tag_list` 时，传递的列表会完全替换原有的 tag_list（系统会自动确保包含 `target` 维度）
- 更新 `field_config` 时，传递的字典会完全替换原有的 field_config

### 请求参数

| 字段         | 类型   | 必选 | 描述                                                               |
|------------|------|----|----------------------------------------------------------------------|
| group_id   | int  | 是  | 自定义时序数据源ID                                           |
| metrics    | list | 是  | 批量指标列表，每个元素为一个指标对象，不能为空                                   |

#### metrics 列表中每个指标对象的字段说明

| 字段         | 类型   | 必选 | 描述                                                       |
|------------|------|----|--------------------------------------------------------------|
| field_id   | int  | 否  | 字段ID，用于定位已存在的指标进行更新。如提供此字段则为更新操作                |
| field_name | string | 否  | 指标字段名称，创建指标时必填，最大长度255。字段名称不能重复              |
| field_scope | string | 否  | 指标数据分组，最大长度255                  |
| tag_list   | list | 否  | Tag列表，维度字段列表。系统会自动添加 `target` 维度（如果不存在）。**注意：更新时为全量替换，需传递完整的 tag 列表**           |
| field_config | dict | 否  | 字段其他配置，详见下方 field_config 字段说明。**注意：更新时为全量替换，需传递完整的配置字典**                                      |
| label      | string | 否  | 指标监控对象，用于标识指标所属的监控对象类型，最大长度255，默认为空字符串          |
| scope_id   | int | 是  | 指标分组ID                                       |

#### field_config 字段说明

`field_config` 是一个字典类型，用于配置指标的额外属性，支持以下字段：

| 字段         | 类型   | 必选 |
|------------|------|-----|
| alias       | string | 否  |
| unit       | string | 否  |
| hidden     | bool | 否  |
| aggregate_method | string | 否  |
| function   | string | 否  |
| interval   | int | 否  |
| disabled   | bool | 否  |

### 请求参数示例

```json
{
  "group_id": 1001,
  "metrics": [
    {
      "field_id": 123,
      "tag_list": ["hostname", "cluster", "region"],
      "field_config": {
        "alias": "CPU使用率（更新）",
        "unit": "percent",
        "aggregate_method": "avg"
      }
    },
    {
      "field_name": "disk_usage",
      "tag_list": ["hostname", "mount_point"],
      "field_config": {
        "alias": "磁盘使用率",
        "unit": "percent",
        "aggregate_method": "avg",
        "interval": 60
      },
      "label": "os"
    },
    {
      "field_name": "api_latency",
      "field_scope": "api_metrics",
      "tag_list": ["hostname", "endpoint"],
      "field_config": {
        "alias": "API延迟",
        "unit": "ms",
        "aggregate_method": "avg"
      },
      "label": "application",
      "scope_id": 1
    }
  ]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 批量操作成功时返回 null     |

### 响应参数示例

```json
{
  "message": "OK",
  "code": 200,
  "data": null,
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```