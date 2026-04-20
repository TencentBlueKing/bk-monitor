### 功能描述

删除快照回溯配置

### 请求参数

| 字段         | 类型   | 必选 | 描述              |
|------------|------|----|-----------------|
| restore_id | int  | 是  | 快照恢复任务ID        |
| operator   | str  | 是  | 操作者             |
| is_sync    | bool | 否  | 是否需要同步，默认为false |

### 请求参数示例

```json
{
    "restore_id": 1,
    "operator": "admin",
    "is_sync": false
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段           | 类型   | 描述       |
|--------------|------|----------|
| restore_id   | int  | 快照恢复任务ID |
| operator     | str  | 操作者      |
| is_sync      | bool | 是否需要同步   |
| bk_tenant_id | str  | 租户ID     |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "restore_id": 1,
        "operator": "admin",
        "is_sync": false,
        "bk_tenant_id": "system"
    }
}
```
