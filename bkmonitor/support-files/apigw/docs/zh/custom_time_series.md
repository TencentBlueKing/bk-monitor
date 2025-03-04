### 功能描述

获取自定义时序列表


#### 接口参数

| 字段          | 类型   | 必选 | 描述             |
|-------------|------|----|----------------|
| bk_biz_id   | int  | 是  | 业务ID           |
| search_key  | str  | 否  | 名称             |
| page_size   | int  | 是  | 获取的条数          |
| page        | int  | 是  | 页数             |
| is_platform | bool | 否  | 是否查询平台级 dataid |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "page_size": 3,
  "page": 1
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 响应数据   |

#### data

| 字段    | 类型   | 描述        |
|-------|------|-----------|
| total | int  | 自定义时序总数   |
| list  | list | 自定义时序详细信息 |

#### data.list

| 字段                     | 类型   | 描述        |
|------------------------|------|-----------|
| time_series_group_id   | int  | 时序分组ID    |
| is_readonly            | bool | 时间序列是否为只读 |
| create_time            | str  | 创建时间      |
| create_user            | str  | 创建用户      |
| update_time            | str  | 最后更新时间    |
| update_user            | str  | 最后更新的用户   |
| is_deleted             | bool | 是否被删除     |
| bk_data_id             | int  | 数据ID      |
| bk_biz_id              | int  | 业务ID      |
| name                   | str  | 名称        |
| scenario               | str  | 监控场景      |
| table_id               | str  | 结果表ID     |
| is_platform            | bool | 是否是平台级    |
| data_label             | str  | 数据标签      |
| protocol               | str  | 上报协议      |
| desc                   | str  | 描述        |
| scenario_display       | list | 场景显示名称的列表 |
| related_strategy_count | int  | 关联的策略数量   |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "list": [
      {
        "time_series_group_id": 474,
        "is_readonly": false,
        "create_time": "2024-08-19 15:43:19+0800",
        "create_user": "xxx",
        "update_time": "2025-02-12 14:34:33+0800",
        "update_user": "xxx",
        "is_deleted": false,
        "bk_data_id": 1573082,
        "bk_biz_id": 2,
        "name": "test_v3_bkbase_test",
        "scenario": "apm",
        "table_id": "2_test_time_series_1573082.__default__",
        "is_platform": false,
        "data_label": "test_v3_bkbase_test",
        "protocol": "json",
        "desc": "test_v3_bkbase_test-test",
        "scenario_display": [
          "用户体验",
          "APM"
        ],
        "related_strategy_count": 0
      },
      {
        "time_series_group_id": 676,
        "is_readonly": false,
        "create_time": "2025-01-15 15:31:53+0800",
        "create_user": "xxx",
        "update_time": "2025-01-15 15:31:53+0800",
        "update_user": "xxx",
        "is_deleted": false,
        "bk_data_id": 524963,
        "bk_biz_id": 2,
        "name": "xxtest",
        "scenario": "application_check",
        "table_id": "2_test_time_series_524963.__default__",
        "is_platform": false,
        "data_label": "xxtest",
        "protocol": "json",
        "desc": "",
        "scenario_display": [
          "用户体验",
          "业务应用"
        ],
        "related_strategy_count": 0
      },
      {
        "time_series_group_id": 600,
        "is_readonly": false,
        "create_time": "2024-11-04 11:25:52+0800",
        "create_user": "xxx",
        "update_time": "2024-11-04 11:25:52+0800",
        "update_user": "xxx",
        "is_deleted": false,
        "bk_data_id": 524858,
        "bk_biz_id": 2,
        "name": "bkbase_v4_new_access_test",
        "scenario": "application_check",
        "table_id": "2_test_time_series_524858.__default__",
        "is_platform": false,
        "data_label": "bkbase_v4_new_access_test",
        "protocol": "json",
        "desc": "bkbase_v4_new_access_test",
        "scenario_display": [
          "用户体验",
          "业务应用"
        ],
        "related_strategy_count": 0
      }
    ],
    "total": 10
  }
}
```
