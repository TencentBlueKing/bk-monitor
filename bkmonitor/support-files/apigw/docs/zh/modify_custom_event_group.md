### 功能描述

修改自定义事件


### 请求参数

| 字段                | 类型         | 必选 | 描述      |
|-------------------|------------|----|---------|
| bk_biz_id         | int        | 是  | 业务ID    |
| bk_event_group_id | int        | 是  | 事件分组ID  |
| name              | str        | 否  | 名称      |
| scenario          | str        | 否  | 监控对象    |
| is_enable         | bool       | 否  | 是否启用    |
| is_platform       | bool       | 否  | 是否为平台事件 |
| data_label        | str        | 否  | 数据别名    |
| event_info_list   | list[dict] | 否  | 事件信息列表  |

#### event_info_list 事件信息列表

| 字段                | 类型         | 必选 | 描述         |
|-------------------|------------|----|------------|
| custom_event_id   | int        | 否  | 事件ID       |
| custom_event_name | str        | 是  | 事件名称       |
| dimension_list    | list[dict] | 是  | 维度列表（不能为空） |

#### event_info_list.dimension_list 维度列表

| 字段             | 类型  | 必选 | 描述                                |
|----------------|-----|----|-----------------------------------|
| dimension_name | str | 是  | 维度字段名称（必须以字母或下划线开头，只能包含字母、数字、下划线） |

### 请求参数示例

```json
{
  "name": "test_custom_event_group",
  "scenario": "apm",
  "data_label": "test_custom_event_group",
  "is_platform": false,
  "bk_biz_id": 2,
  "bk_event_group_id": 32
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 响应数据   |

#### data 响应数据

| 字段                | 类型  | 描述     |
|-------------------|-----|--------|
| bk_event_group_id | int | 事件分组ID |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "bk_event_group_id": 32
  }
}
```

