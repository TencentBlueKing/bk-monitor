### 功能描述

编辑拨测任务组

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段            | 类型   | 必选 | 描述                                      |
|---------------|------|----|-----------------------------------------|
| bk_biz_id     | int  | 是  | 业务ID                                    |
| group_id      | str  | 是  | 拨测任务组ID                                 |
| logo          | str  | 否  | logo图片数据                                |
| name          | str  | 是  | 拨测任务组名字                                 |
| task_id_list  | list | 否  | 拨测任务ID列表（int类型）,传入该参数将覆盖原有的关联任务，不传则保持不变 |

#### 示例数据
```json
{
    "bk_biz_id": 2,
    "group_id": "10002",
    "logo": "",
    "name": "group33",
    "task_id_list": [
        10002,
        10003
    ]
}
```
### 响应参数
| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 数据         |

####  data字段说明
| 字段                 | 类型   | 描述       |
|:-------------------|------|----------|
| id                 | int  | 拨测任务组ID  |
| tasks              | list | 拨测任务列表   |
| create_time        | str  | 创建时间     |
| create_user        | str  | 创建者      |
| update_time        | str  | 更新时间     |
| update_user        | str  | 更新者      |
| is_deleted         | bool | 是否已删除    |
| name               | str  | 拨测任务组名字  |
| logo               | str  | logo图片数据 |
| bk_biz_id          | int  | 业务ID     |

#### data.tasks
| 字段             | 类型    | 描述       |
|----------------|-------|----------|
| id             | int   | 拨测任务ID   |
| config         | dict  | 拨测配置     |
| location       | dict  | 地理位置     |
| nodes          | list  | 拨测节点     |
| groups         | list  | 拨测任务组    |
| available      | float | 拨测任务可用性  |
| task_duration  | float | 拨测任务持续时间 |
| create_time    | str   | 创建时间     |
| create_user    | str   | 创建者      |
| update_time    | str   | 更新时间     |
| update_user    | str   | 更新者      |
| is_deleted     | bool  | 是否已删除    |
| bk_biz_id      | int   | 业务ID     |
| name           | str   | 拨测任务名字   |
| protocol       | str   | 协议       |
| check_interval | int   | 拨测周期(分钟) |
| status         | str   | 拨测当前状态   |

#### data.tasks.config
| 字段                         | 类型    | 描述      |
|----------------------------|-------|---------|
| method                     | str   | 请求方法    |
| authorize                  | dict  | 认证信息    |
| body                       | dict  | 请求主体    |
| headers                    | list  | 请求头     |
| query_params               | list  | 查询参数    |
| ip_list                    | list  | ip列表    |
| url_list                   | float | url列表   |
| port                       | str   | 端口号     |
| response                   | str   | 期待的响应信息 |
| response_code              | str   | 期待返回码   |
| response_format            | str   | 响应格式    |
| target_ip_type             | int   | 目标ip类型  |
| timeout                    | int   | 超时时间    |
| dns_check_mode             | str   | dns检查模式 |
| period                     | int   | 周期      |
| output_fields              | list  | 指定返回的字段 |
| status                     | str   | 拨测当前状态  |

#### data.tasks.config.authorize
| 字段                    | 类型    | 描述       |
|-----------------------|-------|----------|
| auth_type             | str   | 认证类型     |
| auth_config           | dict  | 认证配置     |
| insecure_skip_verify  | bool  | 是否跳过验证   |

#### data.tasks.config.body
| 字段           | 类型   | 描述     |
|--------------|------|--------|
| content      | str  | 主体内容   |
| content_type | str  | 主体类型   |
| data_type    | str  | 数据类型   |
| params       | list | 表单格式数据 |

#### data.tasks.config.headers
| 字段         | 类型  | 描述        |
|------------|-----|-----------|
| is_enabled | str | 是否可用      |
| key        | str | 请求头的key   |
| value      | str | 请求头的value |
| desc       | str | 请求头的描述    |
| index      | str | 请求的位置索引   |

#### data.tasks.config.query_params
| 字段               | 类型  | 描述         |
|------------------|-----|------------|
| is_enabled       | str | 是否可用       |
| key              | str | 查询参数的key   |
| value            | str | 查询参数的value |
| desc             | str | 查询参数的描述    |
| is_builtin       | str | 是否是内置的参数   |

#### data.tasks.location
| 字段                  | 类型   | 描述  |
|---------------------|------|-----|
| bk_state_name       | str  | 国家名 |
| bk_province_name    | str  | 省名  |

#### data.tasks.nodes
| 字段               | 类型   | 描述       |
|------------------|------|----------|
| id               | int  | 拨测节点ID   |
| location         | dict | 节点地区     |
| carrieroperator  | str  | 运营商      |
| ip               | str  | ip地址     |
| bk_cloud_id      | int  | 云区域ID    |
| create_time      | str  | 创建时间     |
| create_user      | str  | 创建者      |
| update_time      | str  | 更新时间     |
| update_user      | str  | 更新者      |
| is_deleted       | bool | 是否已删除    |
| bk_biz_id        | int  | 业务ID     |
| is_common        | bool | 是否是公共节点  |
| biz_scope        | list | 指定业务可见范围 |
| ip_type          | int  | ip类型     |
| name             | str  | 节点名字     |
| bk_host_id       | int  | 主机ID     |

#### data.tasks.groups
| 字段      | 类型  | 描述      |
|---------|-----|---------|
| id      | int | 拨测任务组ID |
| name    | str | 拨测任务组名字 |

#### 示例数据
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": 10002,
        "tasks": [
            {
                "id": 10002,
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
                        "id": 10002,
                        "location": {
                            "country": "中国",
                            "city": "天津"
                        },
                        "carrieroperator": "移动",
                        "ip": "",
                        "bk_cloud_id": 0,
                        "create_time": "2024-09-09 10:52:06+0800",
                        "create_user": "admin",
                        "update_time": "2024-09-09 10:52:06+0800",
                        "update_user": "admin",
                        "is_deleted": false,
                        "bk_biz_id": 2,
                        "is_common": false,
                        "biz_scope": "[]",
                        "ip_type": 4,
                        "name": "node2",
                        "bk_host_id": 124
                    }
                ],
                "groups": [
                    {
                        "id": 10002,
                        "name": "group33"
                    }
                ],
                "available": null,
                "task_duration": null,
                "create_time": "2024-09-09 10:52:45+0800",
                "create_user": "admin",
                "update_time": "2024-09-09 10:53:48+0800",
                "update_user": "admin",
                "is_deleted": false,
                "bk_biz_id": 2,
                "name": "task2",
                "protocol": "HTTP",
                "check_interval": 5,
                "status": "running"
            },
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
                        "id": 10003,
                        "location": {
                            "country": "中国",
                            "city": "山西"
                        },
                        "carrieroperator": "移动",
                        "ip": "",
                        "bk_cloud_id": 0,
                        "create_time": "2024-09-09 10:54:10+0800",
                        "create_user": "admin",
                        "update_time": "2024-09-09 10:54:10+0800",
                        "update_user": "admin",
                        "is_deleted": false,
                        "bk_biz_id": 2,
                        "is_common": false,
                        "biz_scope": "[]",
                        "ip_type": 4,
                        "name": "node3",
                        "bk_host_id": 330
                    }
                ],
                "groups": [
                    {
                        "id": 10002,
                        "name": "group33"
                    }
                ],
                "available": null,
                "task_duration": null,
                "create_time": "2024-09-09 10:57:40+0800",
                "create_user": "admin",
                "update_time": "2024-09-09 10:58:16+0800",
                "update_user": "admin",
                "is_deleted": false,
                "bk_biz_id": 2,
                "name": "task3",
                "protocol": "HTTP",
                "check_interval": 5,
                "status": "running"
            }
        ],
        "create_time": "2024-09-09 15:47:24+0800",
        "create_user": "admin",
        "update_time": "2024-09-09 17:13:37+0800",
        "update_user": "admin",
        "is_deleted": false,
        "name": "group33",
        "logo": "",
        "bk_biz_id": 2
    }
}
```
