### 功能描述

获取单个自定义事件详情

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段                | 类型   | 必选 | 描述       |
|-------------------|------|----|----------|
| bk_event_group_id | int  | 是  | 事件分组ID   |
| time_range        | str  | 是  | 时间范围     |
| need_refresh      | bool | 否  | 是否需要实时刷新 |
| bk_biz_id         | int  | 是  | 业务ID     |
| event_infos_limit | int  | 否  | 事件信息列表上限 |

#### 请求示例

```json
{
  "time_range": "2025-01-20 13:41:51 -- 2025-01-20 14:41:51",
  "bk_event_group_id": 182,
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型   | 描述   |
|---------|------|------|
| result  | bool | 执行结果 |
| code    | int  | 状态码  |
| message | str  | 描述信息 |
| data    | dict | 响应数据 |

#### data 响应数据

| 列名称               | 类型         | 描述          |
|-------------------|------------|-------------|
| bk_event_group_id | int        | 事件组ID       |
| event_info_list   | list[dict] | 自定义事件信息的列表  |
| is_readonly       | bool       | 事件是否为只读     |
| create_time       | str        | 事件创建的时间     |
| create_user       | str        | 创建事件的用户     |
| update_time       | str        | 事件最后更新时间的时间 |
| update_user       | str        | 最后更新事件的用户   |
| is_deleted        | bool       | 事件是否被删除     |
| bk_data_id        | int        | 数据ID        |
| bk_biz_id         | int        | 业务ID        |
| name              | str        | 事件的名称       |
| scenario          | str        | 监控场景        |
| is_enable         | bool       | 是否启用        |
| table_id          | str        | 结果表ID       |
| type              | str        | 事件组类型       |
| is_platform       | bool       | 否为平台事件      |
| data_label        | str        | 数据标签        |
| scenario_display  | list       | 场景显示名称的列表   |
| access_token      | str        | 访问令牌        |

#### data.event_info_list 自定义事件信息的列表

| 列名称                | 类型         | 描述      |
|--------------------|------------|---------|
| custom_event_name  | str        | 事件名称    |
| bk_event_group_id  | int        | 事件组ID   |
| custom_event_id    | int        | 事件ID    |
| related_strategies | list[int]  | 关联的策略ID |
| dimension_list     | list[dict] | 维度列表    |
| event_count        | int        | 事件统计    |
| target_count       | int        | 目标统计    |
| last_change_time   | str        | 最近变更时间  |
| last_event_content | dict       | 最近变更内容  |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "bk_event_group_id": 182,
    "event_info_list": [
      {
        "custom_event_name": "SG_Tcaplus_Alert",
        "bk_event_group_id": 182,
        "custom_event_id": 57673,
        "related_strategies": [],
        "dimension_list": [
          {
            "dimension_name": "target"
          },
          {
            "dimension_name": "module"
          },
          {
            "dimension_name": "location"
          }
        ],
        "event_count": 0,
        "target_count": 0,
        "last_change_time": "",
        "last_event_content": {}
      }
    ],
    "is_readonly": false,
    "create_time": "2024-09-18 17:24:30+0800",
    "create_user": "admin",
    "update_time": "2024-09-18 17:24:30+0800",
    "update_user": "admin",
    "is_deleted": false,
    "bk_data_id": 1574166,
    "bk_biz_id": 2,
    "name": "test_shamcleren",
    "scenario": "kubernetes",
    "is_enable": true,
    "table_id": "2_bkmonitor_event_1574166",
    "type": "custom_event",
    "is_platform": false,
    "data_label": "test_shamcleren",
    "scenario_display": [
      "主机&云平台",
      "kubernetes"
    ],
    "access_token": "xxxx"
  }
}
```

