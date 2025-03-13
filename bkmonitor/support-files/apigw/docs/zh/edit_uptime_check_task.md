### 功能描述

编辑拨测任务


#### 接口参数

| 字段            | 类型        | 必选 | 描述                           |
|---------------|-----------|----|------------------------------|
| bk_biz_id     | int       | 是  | 业务ID                         |
| task_id       | int       | 是  | 拨测任务ID                       |
| protocol      | str       | 是  | 协议                           |
| node_id_list  | list[int] | 是  | 拨测节点ID列表(列表内的节点ID为int类型)     |
| config        | dict      | 是  | 拨测配置                         |
| location      | dict      | 是  | 地理位置                         |
| name          | str       | 是  | 拨测任务名称                       |
| group_id_list | list[int] | 否  | 拨测任务组ID列表(列表内的拨测任务组ID为int类型) |

#### config

| 字段                  | 类型        | 必选 | 描述                                                |
|---------------------|-----------|----|---------------------------------------------------|
| method              | str       | 否  | HTTP 方法，默认值为 "GET"                                |
| authorize           | dict      | 否  | 授权配置                                              |
| body                | dict      | 否  | 请求体                                               |
| query_params        | list      | 否  | 查询参数                                              |
| headers             | list      | 否  | 请求头                                               |
| response_code       | str       | 否  | 响应代码                                              |
| port                | str       | 否  | 端口                                                |
| node_list           | list      | 否  | 主机列表                                              |
| ip_list             | list[str] | 否  | IP 列表                                             |
| output_fields       | list[str] | 否  | 输出字段                                              |
| target_ip_type      | int       | 否  | 目标 IP 类型，默认值为 0                                   |
| dns_check_mode      | str       | 否  | DNS 检查模式，默认值为 "single"                            |
| request             | str       | 否  | 请求内容                                              |
| request_format      | str       | 否  | 请求格式                                              |
| wait_empty_response | bool      | 否  | 是否等待空响应                                           |
| max_rtt             | int       | 否  | 最大往返时间                                            |
| total_num           | int       | 否  | 总数                                                |
| size                | int       | 否  | 数据包大小                                             |
| send_interval       | str       | 否  | 发送间隔                                              |
| target_labels       | dict      | 否  | 目标标签                                              |
| url_list            | list[str] | 否  | URL 列表                                            |
| period              | int       | 是  | 周期                                                |
| response_format     | str       | 否  | 响应格式                                              |
| response            | str       | 否  | 响应内容                                              |
| timeout             | int       | 否  | 超时时间，最大值为 `settings.MAX_AVAILABLE_DURATION_LIMIT` |
| urls                | str       | 否  | URL                                               |
| hosts               | list      | 否  | 主机列表                                              |

#### config.authorize

| 字段                   | 类型   | 必选 | 描述                                                          |
|----------------------|------|----|-------------------------------------------------------------|
| insecure_skip_verify | bool | 否  | 是否跳过 SSL 验证                                                 |
| auth_type            | str  | 是  | 授权类型，包括 "none"、"basic_auth"、"bearer_token" 和 "tencent_auth" |
| auth_config          | dict | 否  | 授权配置，包含具体的认证信息                                              |

#### config.body

| 字段           | 类型   | 必选 | 描述                                                                           |
|--------------|------|----|------------------------------------------------------------------------------|
| data_type    | str  | 否  | 数据类型，默认值为 "text"，可选值包括 "default"、"raw"、"form_data" 和 "x_www_form_urlencoded" |
| params       | list | 否  | 请求参数列表，包含键值对                                                                 |
| content      | str  | 否  | 请求内容，可以为空                                                                    |
| content_type | str  | 否  | 内容类型，默认值为 "text"，可选值包括 "text"、"json"、"html" 和 "xml"                          |

#### config.body.params

| 字段         | 类型   | 必选 | 描述                |
|------------|------|----|-------------------|
| key        | str  | 是  | 键，最大长度为 64 个字符    |
| value      | str  | 否  | 值，可以为空，默认值为空字符串   |
| desc       | str  | 否  | 描述，可以为空，默认值为空字符串  |
| is_builtin | bool | 否  | 是否为内置项，默认值为 False |
| is_enabled | bool | 否  | 是否启用，默认值为 True    |

#### config.query_params

| 字段         | 类型   | 必选 | 描述                  |
|------------|------|----|---------------------|
| key        | str  | 是  | 参数的键，最大长度为 64 个字符   |
| value      | str  | 否  | 参数的值，可以为空，默认值为空字符串  |
| desc       | str  | 否  | 参数的描述，可以为空，默认值为空字符串 |
| is_builtin | bool | 否  | 是否为内置项，默认值为 False   |
| is_enabled | bool | 否  | 是否启用，默认值为 True      |

#### config.headers

| 字段         | 类型  | 描述        |
|------------|-----|-----------|
| is_enabled | str | 是否可用      |
| key        | str | 请求头的key   |
| value      | str | 请求头的value |
| desc       | str | 请求头的描述    |
| index      | str | 请求的位置索引   |

#### config.node_list

| 字段          | 类型  | 必选 | 描述                     |
|-------------|-----|----|------------------------|
| bk_host_id  | int | 否  | 主机 ID，允许为空             |
| ip          | str | 否  | 主机 IP，可以为空             |
| outer_ip    | str | 否  | 外部 IP，可以为空，兼容通过文件导入的任务 |
| target_type | str | 否  | 目标类型，可以为空              |
| bk_biz_id   | int | 否  | 业务 ID，允许为空             |
| bk_inst_id  | int | 否  | 实例 ID，允许为空             |
| bk_obj_id   | str | 否  | 对象 ID，可以为空             |
| node_path   | str | 否  | 节点路径，可以为空              |

#### config.target_labels

- 字段名是 目标主机IP 或者是 url
- 字段值是 目标主机的标签

#### config.hosts

| 字段          | 类型  | 必选 | 描述   |
|-------------|-----|----|------|
| bk_host_id  | int | 否  | 主机ID |
| ip          | str | 否  | 主机IP |
| outer_ip    | str | 否  | 外部IP |
| target_type | str | 否  | 目标类型 |
| bk_biz_id   | int | 否  | 业务ID |
| bk_inst_id  | int | 否  | 实例ID |
| bk_obj_id   | str | 否  | 对象ID |
| node_path   | str | 否  | 节点路径 |

#### location

| 字段               | 类型  | 描述  |
|------------------|-----|-----|
| bk_state_name    | str | 国家名 |
| bk_province_name | str | 省名  |

#### 示例数据

```json
{
  "bk_biz_id": 2,
  "task_id": 10003,
  "protocol": "HTTP",
  "node_id_list": [
    10004
  ],
  "config": {
    "period": 60,
    "timeout": 3000,
    "response": "",
    "response_format": "nin",
    "method": "GET",
    "url_list": [
      "http://www.baidu.com"
    ],
    "headers": [],
    "body": {
      "data_type": "default",
      "params": [],
      "content": "",
      "content_type": ""
    },
    "authorize": {
      "auth_type": "none",
      "auth_config": {},
      "insecure_skip_verify": false
    },
    "query_params": [],
    "response_code": ""
  },
  "location": {
    "bk_state_name": "",
    "bk_province_name": ""
  },
  "name": "task4_3",
  "group_id_list": [
    10001
  ]
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

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
| plat_id         | int       | 云区域ID    |
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
  "data": {
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
      "request": null,
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
        "location": {
          "country": "中国",
          "city": "北京"
        },
        "carrieroperator": "移动",
        "ip": "",
        "bk_cloud_id": 0,
        "create_time": "2024-12-12 17:30:30+0800",
        "create_user": "admin",
        "update_time": "2024-12-12 17:30:30+0800",
        "update_user": "admin",
        "is_deleted": false,
        "bk_biz_id": 2,
        "is_common": false,
        "biz_scope": "[]",
        "ip_type": 4,
        "name": "node4",
        "bk_host_id": 263
      }
    ],
    "groups": [
      {
        "id": 10001,
        "name": "group2"
      }
    ],
    "available": null,
    "task_duration": null,
    "create_time": "2024-12-12 17:31:40+0800",
    "create_user": "admin",
    "update_time": "2025-01-20 15:50:17+0800",
    "update_user": "admin",
    "is_deleted": false,
    "bk_biz_id": 2,
    "name": "task4_3",
    "protocol": "HTTP",
    "labels": {},
    "indepentent_dataid": false,
    "check_interval": 5,
    "status": "running"
  }
}
```