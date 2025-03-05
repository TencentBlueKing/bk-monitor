### 功能描述

获取拨测任务列表


#### 接口参数

`查询字符串参数`

| 字段                | 类型   | 必选 | 描述           |
|-------------------|------|----|--------------|
| bk_biz_id         | int  | 是  | 业务ID         |
| get_available     | bool | 否  | 是否获取拨测任务可用性  |
| get_task_duration | bool | 否  | 是否获取拨测任务持续时间 |

#### 示例数据

`查询字符串参数`

```json
{
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型         | 描述     |
|---------|------------|--------|
| result  | bool       | 请求是否成功 |
| code    | int        | 返回的状态码 |
| message | str        | 描述信息   |
| data    | list[dict] | 数据     |

#### data

| 字段                 | 类型         | 描述                                 |
|--------------------|------------|------------------------------------|
| bk_biz_id          | int        | 业务ID                               |
| id                 | int        | 拨测任务ID                             |
| name               | str        | 任务名称                               |
| protocol           | str        | 协议                                 |
| labels             | dict       | 自定义标签                              |
| indepentent_dataid | bool       | 独立业务数据ID                           |
| check_interval     | int        | 拨测周期(分钟)                           |
| location           | dict       | 地区                                 |
| nodes              | list[dict] | 拨测节点                               |
| status             | str        | 当前状态                               |
| config             | dict       | 拨测配置，与入参config字段结构一致               |
| create_time        | str        | 创建时间,例如："2025-01-16 15:28:31+0800" |
| create_user        | str        | 创建人                                |
| update_time        | str        | 修改时间,例如："2025-01-16 15:28:31+0800" |
| update_user        | str        | 修改人                                |
| is_deleted         | bool       | 是否删除                               |
| available          | float      | 拨测任务可用性                            |
| task_duration      | float      | 拨测任务持续时间                           |
| groups             | list       | 拨测任务组                              |

#### data.location

| 字段               | 类型  | 描述  |
|------------------|-----|-----|
| bk_state_name    | str | 国家名 |
| bk_province_name | str | 省名  |

#### data.nodes

| 字段              | 类型        | 描述       |
|-----------------|-----------|----------|
| bk_biz_id       | int       | 业务ID     |
| id              | int       | 拨测节点ID   |
| is_common       | bool      | 是否为通用节点  |
| biz_scope       | list[int] | 指定业务可见范围 |
| ip_type         | int       | IP类型     |
| name            | str       | 节点名称     |
| ip              | str       | IP地址     |
| bk_host_id      | int       | 主机ID     |
| location        | dict      | 地区       |
| carrieroperator | str       | 外网运营商    |
| bk_cloud_id     | int       | 云区域ID    |
| bk_host_id      | int       | 主机ID     |
| create_time     | str       | 创建时间     |
| create_user     | str       | 创建者      |
| update_time     | str       | 更新时间     |
| update_user     | str       | 更新者      |
| is_deleted      | bool      | 是否已删除    |

#### data.nodes.location

| 字段      | 类型  | 描述  |
|---------|-----|-----|
| country | str | 国家名 |
| city    | str | 城市名 |

#### data.groups

| 字段   | 类型  | 描述      |
|------|-----|---------|
| id   | int | 拨测任务组ID |
| name | str | 拨测任务组名称 |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 10003,
      "config": {
        "method": "GET",
        "authorize": {
          "auth_type": "none",
          "auth_config": {},
          "insecure_skip_verify": false
        },
        "body": {
          "data_type": "default",
          "params": [],
          "content": "",
          "content_type": ""
        },
        "query_params": [],
        "headers": [],
        "response_code": "",
        "ip_list": [],
        "output_fields": [
          "bk_host_innerip",
          "bk_host_innerip_v6"
        ],
        "target_ip_type": 0,
        "dns_check_mode": "single",
        "url_list": [
          "http://www.baidu.com"
        ],
        "period": 60,
        "response_format": "nin",
        "response": "",
        "timeout": 3000
      },
      "location": {
        "bk_state_name": "",
        "bk_province_name": ""
      },
      "nodes": [
        {
          "id": 10004,
          "create_user": "admin",
          "update_user": "admin",
          "is_deleted": false,
          "bk_biz_id": 2,
          "is_common": false,
          "biz_scope": [],
          "ip_type": 4,
          "name": "node4",
          "ip": "",
          "bk_host_id": 263,
          "bk_cloud_id": 0,
          "location": {
            "country": "中国",
            "city": "北京"
          },
          "carrieroperator": "移动"
        }
      ],
      "groups": [
        {
          "id": 10001,
          "name": "group2"
        }
      ],
      "available": 0.0,
      "task_duration": 0.0,
      "url": [
        "http://www.baidu.com"
      ],
      "create_time": "2024-12-12 17:31:40+0800",
      "update_time": "2025-01-20 15:50:17+0800",
      "create_user": "admin",
      "update_user": "admin",
      "is_deleted": false,
      "bk_biz_id": 2,
      "name": "task4_3",
      "protocol": "HTTP",
      "labels": {},
      "indepentent_dataid": false,
      "check_interval": 5,
      "status": "running"
    },
    {
      "id": 10005,
      "config": {
        "method": "GET",
        "authorize": {
          "auth_type": "none",
          "auth_config": {},
          "insecure_skip_verify": false
        },
        "body": {
          "data_type": "default",
          "params": [],
          "content": "",
          "content_type": ""
        },
        "query_params": [],
        "headers": [],
        "response_code": "",
        "ip_list": [],
        "output_fields": [
          "bk_host_innerip",
          "bk_host_innerip_v6"
        ],
        "target_ip_type": 0,
        "dns_check_mode": "single",
        "url_list": [
          "http://www.baidu.com"
        ],
        "period": 60,
        "response_format": "nin",
        "response": "",
        "timeout": 3000
      },
      "location": {
        "bk_state_name": "",
        "bk_province_name": ""
      },
      "nodes": [
        {
          "id": 10006,
          "create_user": "admin",
          "update_user": "admin",
          "is_deleted": false,
          "bk_biz_id": 2,
          "is_common": false,
          "biz_scope": [],
          "ip_type": 4,
          "name": "node6",
          "ip": "",
          "bk_host_id": 462,
          "bk_cloud_id": 0,
          "location": {
            "country": "中国",
            "city": "河北"
          },
          "carrieroperator": "移动"
        }
      ],
      "groups": [],
      "available": 0.0,
      "task_duration": 0.0,
      "url": [
        "http://www.baidu.com"
      ],
      "create_time": "2024-12-12 18:08:45+0800",
      "update_time": "2024-12-12 18:09:04+0800",
      "create_user": "admin",
      "update_user": "admin",
      "is_deleted": false,
      "bk_biz_id": 2,
      "name": "task6",
      "protocol": "HTTP",
      "labels": {},
      "indepentent_dataid": false,
      "check_interval": 5,
      "status": "start_failed"
    }
  ]
}
```