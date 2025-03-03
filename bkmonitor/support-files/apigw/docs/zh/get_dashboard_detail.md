### 功能描述

获取仪表盘目录树

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段            | 类型     | 必选 | 描述     |
|---------------|--------|----|--------|
| bk_biz_id     | int    | 是  | 业务ID   |
| dashboard_uid | string | 是  | 仪表盘UID |

#### 示例数据

```json
{
  "bk_biz_id": 2,
  "dashboard_uid": "ycBx0NFVz"
}
```

### 响应参数

| 字段      | 类型     | 描述      |
|---------|--------|---------|
| id      | int    | 仪表盘ID   |
| uid     | string | 仪表盘UID  |
| title   | string | 仪表盘名称   |
| data    | dict   | 仪表盘配置   |
| version | int    | 仪表盘版本   |
| slug    | string | 仪表盘slug |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 54,
    "uid": "ycBx0NFVz",
    "title": "bkcheck",
    "data": {},
    "version": 1,
    "slug": ""
  }
}
```
