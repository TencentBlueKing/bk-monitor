### 功能描述

批量创建或更新自定义时序指标
- 如果指标中提供了 field_id，则更新对应的指标
- 如果未提供 field_id，则创建新指标（此时 group_id 和 field_name 为必填项）


### 请求参数

| 字段         | 类型   | 必选 | 描述                                                               |
|------------|------|----|----------------------------------------------------------------------|
| bk_tenant_id | string | 是  | 租户ID，用于标识数据所属租户                                             |
| metrics    | list | 是  | 批量指标列表，每个元素为一个指标对象，不能为空                                   |

#### metrics 列表中每个指标对象的字段说明

| 字段         | 类型   | 必选 | 描述                                                               |
|------------|------|----|----------------------------------------------------------------------|
| field_id   | int  | 否  | 字段ID，用于定位已存在的指标进行更新。如提供此字段则为更新操作                        |
| group_id   | int  | 否  | 自定义时序数据源ID，创建指标时必填                                           |
| field_name | string | 否  | 指标字段名称，创建指标时必填，最大长度255。字段名称不能重复                  |
| tag_list   | list | 否  | Tag列表，维度字段列表。系统会自动添加 `target` 维度（如果不存在）                   |
| field_config | dict | 否  | 字段其他配置，详见下方 field_config 字段说明                                              |
| label      | string | 否  | 指标监控对象，用于标识指标所属的监控对象类型，最大长度255，默认为空字符串                  |
| service_name | string | 否  | 服务名称，最大长度255。如果提供了此字段，则 field_scope 会被设置为 `{service_name}||default`；否则 field_scope 为 `default`                  |

#### field_config 字段说明

`field_config` 是一个字典类型，用于配置指标的额外属性，支持以下字段：

| 字段         | 类型   | 必选 |
|------------|------|-----|
| desc       | string | 否  |
| unit       | string | 否  |
| hidden     | bool | 否  |
| aggregate_method | string | 否  |
| function   | string | 否  |
| interval   | int | 否  |
| disabled   | bool | 否  |

### 请求参数示例

```json
{
  "bk_tenant_id": "bk_tenant_001",
  "metrics": [
    {
      "field_id": 123,
      "tag_list": ["hostname", "cluster", "region"],
      "field_config": {
        "desc": "CPU使用率（更新）",
        "unit": "percent",
        "aggregate_method": "avg"
      }
    },
    {
      "group_id": 1001,
      "field_name": "disk_usage",
      "tag_list": ["hostname", "mount_point"],
      "field_config": {
        "desc": "磁盘使用率",
        "unit": "percent",
        "aggregate_method": "avg",
        "interval": 60
      },
      "label": "os"
    },
    {
      "group_id": 1002,
      "field_name": "api_latency",
      "service_name": "api-server",
      "tag_list": ["hostname", "endpoint"],
      "field_config": {
        "desc": "API延迟",
        "unit": "ms",
        "aggregate_method": "avg"
      },
      "label": "application"
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