### 功能描述

【告警V2】主机目标查询

### 请求参数

| 字段       | 类型  | 必选 | 描述   |
|----------|-----|----|------|
| alert_id | str | 是  | 告警ID |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 主机目标列表 |

#### data 元素字段说明

| 字段           | 类型     | 描述           |
|--------------|--------|--------------|
| bk_host_id   | int    | 主机ID         |
| bk_target_ip | string | 目标IP         |
| bk_cloud_id  | int    | 云区域ID        |
| display_name | string | 显示名称（包含拓扑路径） |
| bk_host_name | string | 主机名称         |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "bk_host_id": 1001,
            "bk_target_ip": "127.0.0.1",
            "bk_cloud_id": 0,
            "display_name": "蓝鲸 / 作业平台 / job-manage / 127.0.0.1",
            "bk_host_name": "job-manage-01"
        },
        {
            "bk_host_id": 1002,
            "bk_target_ip": "127.0.0.2",
            "bk_cloud_id": 0,
            "display_name": "蓝鲸 / 作业平台 / job-execute / 127.0.0.2",
            "bk_host_name": "job-execute-01"
        }
    ]
}
```
