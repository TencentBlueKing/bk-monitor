### 功能描述

查询事件分组

### 请求参数

| 字段               | 类型        | 必选 | 描述           |
|------------------|-----------|----|--------------| 
| label            | string    | 否  | 事件分组标签（监控对象） |
| event_group_name | string    | 否  | 事件分组名称       |
| bk_biz_id        | int       | 否  | 业务ID         |
| bk_data_ids      | list[int] | 否  | 数据源ID列表      |
| page             | int       | 否  | 页码，默认为1      |
| page_size        | int       | 否  | 每页数量，默认为0    |

### 请求参数示例

```json
{
  "label": "application",
  "event_group_name": "事件分组名",
  "bk_biz_id": 123,
  "bk_data_ids": [1001, 1002],
  "page": 1,
  "page_size": 10
}
```

### 响应参数

| 字段         | 类型          | 描述                                      |
|------------|-------------|-----------------------------------------|
| result     | bool        | 请求是否成功                                  |
| code       | int         | 返回的状态码                                  |
| message    | string      | 描述信息                                    |
| data       | list/object | 数据（非分页时为list，分页时为object，包含count和info字段） |
| request_id | string      | 请求ID                                    |

#### data字段说明（分页返回，当page_size > 0时）

| 字段    | 类型   | 描述     |
|-------|------|--------|
| count | int  | 总数     |
| info  | list | 事件分组列表 |

#### data字段说明（非分页返回，当page_size <= 0时）

data直接为事件分组列表（list类型）

#### data.info（分页）或 data（非分页）列表项字段说明

| 字段                | 类型     | 描述     |
|-------------------|--------|--------|
| event_group_id    | int    | 事件分组ID |
| bk\_data_id       | int    | 数据源ID  |
| bk\_biz_id        | int    | 业务ID   |
| table_id          | string | 结果表ID  |
| event\_group_name | string | 事件分组名  |
| label             | string | 事件标签   |
| is_enable         | bool   | 是否启用   |
| creator           | string | 创建者    |
| create_time       | string | 创建时间   |
| last_modify_user  | string | 最后修改者  |
| last_modify_time  | string | 最后修改时间 |
| event_info_list   | list   | 事件列表   |
| data_label        | string | 数据标签   |
| status            | string | 状态     |

#### event_info_list具体内容说明

| 字段             | 类型        | 描述     |
|----------------|-----------|--------|
| bk\_event_id   | int       | 事件ID   |
| event_name     | string    | 事件名    |
| dimension_list | list[str] | 维度名称列表 |

### 响应参数示例

#### 分页返回示例（page_size > 0）

```json
{
  "message": "OK",
  "code": 200,
  "data": {
    "count": 100,
    "info": [
      {
        "event_group_id": 1001,
        "bk_data_id": 123,
        "bk_biz_id": 123,
        "table_id": "123_bkmonitor_event_123",
        "event_group_name": "事件分组名",
        "label": "application",
        "is_enable": true,
        "creator": "admin",
        "create_time": "2019-10-10 10:10:10",
        "last_modify_user": "admin",
        "last_modify_time": "2020-10-10 10:10:10",
        "event_info_list": [
          {
            "bk_event_id": 1,
            "event_name": "usage for update",
            "dimension_list": ["field_name", "target"]
          },
          {
            "bk_event_id": 2,
            "event_name": "usage for create",
            "dimension_list": ["field_name", "target"]
          }
        ],
        "data_label": "custom_event",
        "status": "normal"
      }
    ]
  },
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```

#### 非分页返回示例（page_size <= 0）

```json
{
  "message": "OK",
  "code": 200,
  "data": [
    {
      "event_group_id": 1001,
      "bk_data_id": 123,
      "bk_biz_id": 123,
      "table_id": "123_bkmonitor_event_123",
      "event_group_name": "事件分组名",
      "label": "application",
      "is_enable": true,
      "creator": "admin",
      "create_time": "2019-10-10 10:10:10",
      "last_modify_user": "admin",
      "last_modify_time": "2020-10-10 10:10:10",
      "event_info_list": [
        {
          "bk_event_id": 1,
          "event_name": "usage for update",
          "dimension_list": ["field_name", "target"]
        },
        {
          "bk_event_id": 2,
          "event_name": "usage for create",
          "dimension_list": ["field_name", "target"]
        }
      ],
      "data_label": "custom_event",
      "status": "normal"
    }
  ],
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```
