### 功能描述

查询自定义事件列表


#### 接口参数

| 字段          | 类型   | 必选 | 描述                                     |
|-------------|------|----|----------------------------------------|
| bk_biz_id   | int  | 是  | 业务ID                                   |
| search_key  | str  | 否  | 查询关键字，可用于对name进行模糊查询，以及对pk或者数据ID进行精确查询 |
| page_size   | int  | 否  | 获取条数，默认值10                             |
| page        | int  | 否  | 页数，默认值1                                |
| is_platform | bool | 否  | 是否是平台级                                 |

#### 请求示例

```json
{
  "page": 1,
  "page_size": 100,
  "bk_biz_id": 2
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

| 字段    | 类型         | 描述   |
|-------|------------|------|
| list  | list[dict] | 事件列表 |
| total | int        | 事件总数 |

#### data.list 事件列表信息

| 列名称                    | 类型   | 描述        |
|------------------------|------|-----------|
| bk_event_group_id      | int  | 事件组ID     |
| is_readonly            | bool | 事件是否为只读   |
| create_time            | str  | 事件创建的时间   |
| create_user            | str  | 创建事件的用户   |
| update_time            | str  | 事件最后更新时间  |
| update_user            | str  | 最后更新事件的用户 |
| is_deleted             | bool | 事件是否被删除   |
| bk_data_id             | int  | 数据ID      |
| bk_biz_id              | int  | 业务ID      |
| name                   | str  | 事件名称      |
| scenario               | str  | 监控场景      |
| is_enable              | bool | 是否启用      |
| table_id               | str  | 结果表ID     |
| type                   | str  | 事件的类型     |
| is_platform            | bool | 是否为平台事件   |
| data_label             | str  | 数据标签      |
| scenario_display       | list | 场景显示名称的列表 |
| related_strategy_count | int  | 相关策略的数量   |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "list": [
      {
        "bk_event_group_id": 32,
        "is_readonly": false,
        "create_time": "2025-01-16 15:38:11+0800",
        "create_user": "admin",
        "update_time": "2025-01-16 15:38:11+0800",
        "update_user": "admin",
        "is_deleted": false,
        "bk_data_id": 1573900,
        "bk_biz_id": 2,
        "name": "test_custom_event_group",
        "scenario": "apm",
        "is_enable": true,
        "table_id": "2_bkmonitor_event_1573900",
        "type": "custom_event",
        "is_platform": false,
        "data_label": "test_custom_event_group",
        "scenario_display": [
          "用户体验",
          "APM"
        ],
        "related_strategy_count": 0
      },
      {
        "bk_event_group_id": 28,
        "is_readonly": false,
        "create_time": "2024-09-23 16:14:23+0800",
        "create_user": "admin",
        "update_time": "2024-09-23 16:14:23+0800",
        "update_user": "admin",
        "is_deleted": false,
        "bk_data_id": 1574272,
        "bk_biz_id": 2,
        "name": "zw_test3",
        "scenario": "application_check",
        "is_enable": true,
        "table_id": "2_bkmonitor_event_1574272",
        "type": "custom_event",
        "is_platform": false,
        "data_label": "zw_test3",
        "scenario_display": [
          "用户体验",
          "业务应用"
        ],
        "related_strategy_count": 0
      }
    ],
    "total": 2
  }
}
```

