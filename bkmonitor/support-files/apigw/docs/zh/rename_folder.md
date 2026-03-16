### 功能描述

重命名指定文件夹

### 请求参数

| 字段        | 类型     | 必选 | 描述      |
|-----------|--------|----|---------|
| bk_biz_id | int    | 是  | 业务ID    |
| uid       | string | 是  | 文件夹唯一标识 |
| title     | string | 是  | 新的文件夹名称 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "uid": "folder-abc123",
    "title": "新的监控面板"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | object | 返回数据   |

#### data 字段说明

| 字段        | 类型     | 描述               |
|-----------|--------|------------------|
| id        | int    | 文件夹ID            |
| uid       | string | 文件夹唯一标识          |
| orgId     | int    | 组织ID             |
| title     | string | 更新后的文件夹名称        |
| url       | string | 文件夹访问URL         |
| hasAcl    | bool   | 是否有访问控制列表        |
| canSave   | bool   | 是否可保存            |
| canEdit   | bool   | 是否可编辑            |
| canAdmin  | bool   | 是否有管理权限          |
| canDelete | bool   | 是否可删除            |
| createdBy | string | 创建者用户名           |
| created   | string | 创建时间（ISO 8601格式） |
| updatedBy | string | 更新者用户名           |
| updated   | string | 更新时间（ISO 8601格式） |
| version   | int    | 版本号              |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "",
    "data": {
        "id": 243,
        "uid": "J0ZxMV4Nz",
        "orgId": 0,
        "title": "tyx_测试_2",
        "url": "/grafana/dashboards/f/J0ZxMV4Nz/tyx-e6b58b-e8af95-2",
        "hasAcl": false,
        "canSave": true,
        "canEdit": true,
        "canAdmin": true,
        "canDelete": true,
        "createdBy": "admin",
        "created": "2024-12-02T09:47:52Z",
        "updatedBy": "admin",
        "updated": "2026-02-12T08:35:37Z",
        "version": 2
    }
}
```
