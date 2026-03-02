### 功能描述

查询组内人员

### 请求参数

| 字段        | 类型  | 必选 | 描述   |
|-----------|-----|----|------|
| bk_biz_id | int | 否  | 业务ID |

### 请求参数示例

```json
{
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 组列表数据  |

#### data 元素字段说明

| 字段           | 类型        | 描述           |
|--------------|-----------|--------------|
| id           | string    | 组ID          |
| display_name | string    | 组显示名称        |
| logo         | string    | 组图标          |
| type         | string    | 类型（固定为group） |
| children     | list[str] | 组内人员列表       |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": "bk_biz_maintainer",
      "display_name": "运维人员",
      "logo": "",
      "type": "group",
      "children": ["user1", "user2", "user3"]
    },
    {
      "id": "bk_biz_productor",
      "display_name": "产品人员",
      "logo": "",
      "type": "group",
      "children": ["user4", "user5"]
    },
    {
      "id": "bk_biz_tester",
      "display_name": "测试人员",
      "logo": "",
      "type": "group",
      "children": ["user6", "user7"]
    },
    {
      "id": "bk_biz_developer",
      "display_name": "开发人员",
      "logo": "",
      "type": "group",
      "children": ["user8", "user9"]
    },
    {
      "id": "bk_biz_controller",
      "display_name": "配置管理人员",
      "logo": "",
      "type": "group",
      "children": ["user10"]
    },
    {
      "id": "bk_biz_notify_receiver",
      "display_name": "告警接收人员",
      "logo": "",
      "type": "group",
      "children": ["user11", "user12"]
    }
  ]
}
```
