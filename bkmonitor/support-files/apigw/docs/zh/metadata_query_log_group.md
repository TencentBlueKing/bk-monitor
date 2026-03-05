### 功能描述

查询日志分组

### 请求参数

| 字段             | 类型     | 必选 | 描述          |
|----------------|--------|----|-------------|
| label          | string | 否  | 日志分组标签，默认为空 |
| log_group_name | string | 否  | 日志分组名称，默认为空 |
| bk_biz_id      | string | 否  | 业务ID，默认为空   |

### 请求参数示例

```json
{
    "bk_biz_id": "2",
    "label": "application"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 数据     |

#### data 元素字段说明

| 字段               | 类型     | 描述      |
|------------------|--------|---------|
| log_group_id     | int    | 日志分组ID  |
| bk_tenant_id     | string | 租户ID    |
| bk_data_id       | int    | 数据源ID   |
| bk_biz_id        | int    | 业务ID    |
| table_id         | string | 结果表ID   |
| log_group_name   | string | 日志分组名   |
| label            | string | 日志分组标签  |
| is_enable        | bool   | 是否启用    |
| bk_data_token    | string | 上报Token |
| creator          | string | 创建人     |
| create_time      | string | 创建时间    |
| last_modify_user | string | 最后更新人   |
| last_modify_time | string | 最后更新时间  |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "log_group_id": 1,
            "bk_tenant_id": "default",
            "bk_data_id": 1500001,
            "bk_biz_id": 2,
            "table_id": "2_bklog.test_log",
            "log_group_name": "test_log",
            "label": "application",
            "is_enable": true,
            "bk_data_token": "",
            "creator": "admin",
            "create_time": "2021-10-10 10:10:10",
            "last_modify_user": "admin",
            "last_modify_time": "2021-10-10 10:10:10"
        }
    ],
    "result": true
}
```
