### 功能描述

创建仪表盘或文件夹

### 请求参数

| 字段        | 类型     | 必选 | 描述                                    |
|-----------|--------|----|---------------------------------------|
| bk_biz_id | int    | 是  | 业务ID                                  |
| title     | string | 是  | 名称                                    |
| type      | string | 是  | 类型，可选值：`dashboard`（仪表盘）、`folder`（文件夹） |
| folderId  | int    | 否  | 文件夹ID，默认为0（General目录）。仅在创建仪表盘时有效      |

### 请求参数示例

**创建仪表盘**：

```json
{
    "bk_biz_id": 2,
    "title": "我的仪表盘",
    "type": "dashboard",
    "folderId": 0
}
```

**创建文件夹**：

```json
{
    "bk_biz_id": 2,
    "title": "监控面板",
    "type": "folder"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | object | 返回数据   |

#### data 字段说明（创建仪表盘时）

| 字段          | 类型     | 描述              |
|-------------|--------|-----------------|
| uid         | string | 仪表盘唯一标识         |
| pluginId    | string | 插件ID            |
| title       | string | 仪表盘标题           |
| imported    | bool   | 是否已导入           |
| importedUri | string | 导入的URI          |
| importedUrl | string | 导入的URL（仪表盘访问地址） |
| slug        | string | URL友好的标识符       |
| dashboardId | int    | 仪表盘ID           |
| folderId    | int    | 所属文件夹ID         |
| folderUid   | string | 所属文件夹唯一标识       |
| description | string | 描述信息            |
| path        | string | 路径              |
| removed     | bool   | 是否已删除           |

#### data 字段说明（创建文件夹时）

| 字段        | 类型     | 描述               |
|-----------|--------|------------------|
| id        | int    | 文件夹ID            |
| uid       | string | 文件夹唯一标识          |
| orgId     | int    | 组织ID             |
| title     | string | 文件夹名称            |
| url       | string | 文件夹访问URL         |
| hasAcl    | bool   | 是否有访问控制列表        |
| canSave   | bool   | 是否可保存            |
| canEdit   | bool   | 是否可编辑            |
| canAdmin  | bool   | 是否可管理            |
| canDelete | bool   | 是否可删除            |
| createdBy | string | 创建人              |
| created   | string | 创建时间（ISO 8601格式） |
| updatedBy | string | 更新人              |
| updated   | string | 更新时间（ISO 8601格式） |
| version   | int    | 版本号              |

### 响应参数示例

**创建仪表盘成功**：

```json
{
    "result": true,
    "code": 200,
    "message": "",
    "data": {
        "uid": "efd01oj40ip6oe",
        "pluginId": "",
        "title": "test",
        "imported": true,
        "importedUri": "db/test",
        "importedUrl": "/grafana/d/efd01oj40ip6oe/test",
        "slug": "test",
        "dashboardId": 587,
        "folderId": 586,
        "folderUid": "cfd01k7lc3oqoe",
        "description": "",
        "path": "",
        "removed": false
    }
}
```

**创建文件夹成功**：

```json
{
    "result": true,
    "code": 200,
    "message": "",
    "data": {
        "id": 586,
        "uid": "cfd01k7lc3oqoe",
        "orgId": 0,
        "title": "test",
        "url": "/grafana/dashboards/f/cfd01k7lc3oqoe/test",
        "hasAcl": false,
        "canSave": true,
        "canEdit": true,
        "canAdmin": true,
        "canDelete": true,
        "createdBy": "admin",
        "created": "2026-02-12T08:12:48.310617769Z",
        "updatedBy": "admin",
        "updated": "2026-02-12T08:12:48.310617858Z",
        "version": 1
    }
}
```
