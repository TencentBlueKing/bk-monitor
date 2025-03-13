### 功能描述

获取仪表盘目录树


#### 接口参数

| 字段        | 类型  | 必选 | 描述   |
|-----------|-----|----|------|
| bk_biz_id | int | 是  | 业务ID |

#### 示例数据

```json
{
  "bk_biz_id": 2
}
```

### 响应参数

| 字段         | 类型     | 描述    |
|------------|--------|-------|
| title      | string | 目录名称  |
| dashboards | list   | 仪表盘列表 |

#### dashboards 字段

| 字段        | 类型     | 描述       |
|-----------|--------|----------|
| id        | int    | 仪表盘ID    |
| title     | string | 仪表盘名称    |
| uri       | string | 仪表盘URI   |
| url       | string | 仪表盘URL   |
| slug      | string | 仪表盘slug  |
| tags      | list   | 仪表盘标签    |
| isStarred | bool   | 仪表盘是否已收藏 |
| editable  | bool   | 仪表盘是否可编辑 |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "dashboards": [
        {
          "id": 54,
          "uid": "ycBx0NFVz",
          "title": "bkcheck",
          "uri": "db/bkcheck",
          "url": "/grafana/d/ycBx0NFVz/bkcheck",
          "slug": "",
          "tags": [],
          "isStarred": false,
          "editable": true
        }
      ],
      "title": "General"
    }
  ]
}
```
