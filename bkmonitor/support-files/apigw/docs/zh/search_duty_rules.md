### 功能描述

查询轮值规则列表


### 请求参数

| 字段         | 类型   | 必选  | 描述     |
|------------|------|-----|--------|
| bk_biz_ids | list[int] | 否   | 业务ID列表   |
| ids        | list[int] | 否   | 轮值规则ID列表 |
| name       | str  | 否   | 轮值规则名称（支持模糊搜索） |

### 请求参数示例

```json
{
  "bk_biz_ids": [
    2
  ],
  "ids": [1],
  "name": "test"
}
```

### 响应参数

| 字段         | 类型           | 描述        |
|------------|--------------|-----------|
| result     | bool         | 请求是否成功    |
| code       | int          | 返回的状态码    |
| message    | string       | 描述信息      |
| data       | list[object] | 数据        |
| request_id | str          | ESB记录请求ID |

#### data字段元素说明

| 字段               | 类型        | 必须  | 描述                                   |
|------------------|-----------|-----|--------------------------------------|
| id               | int       | 是   | 轮值规则ID                        |
| bk_biz_id        | int       | 是   | 业务ID                                 |
| name             | string    | 是   | 轮值规则名称                                   |
| enabled          | bool      | 是   | 是否开启                                 |
| category         | string    | 是   | 轮值类型 `regular(日常值班)` `handoff(交替轮值)` |
| labels           | list[str] | 是   | 规则标签                                 |
| effective_time   | string    | 是   | 生效时间， 格式 `2022-03-11 00:00:00`       |
| end_time         | string    | 否   | 截止时间， 格式 `2022-03-11 00:00:00`       |
| create_time      | string    | 是   | 创建时间                                 |
| create_user      | string    | 是   | 创建人                                   |
| update_time      | string    | 是   | 更新时间                                 |
| update_user      | string    | 是   | 更新人                                   |
| user_groups      | list[int] | 是   | 关联的用户组ID列表                         |
| user_groups_count| int       | 是   | 关联的用户组数量                           |
| delete_allowed   | bool      | 是   | 是否可删除（当user_groups_count为0时可删除）                                |
| edit_allowed     | bool      | 是   | 是否可编辑（当bk_biz_id不为0时可编辑）                                |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 62,
      "name": "企业微信机器人1234",
      "bk_biz_id": 2,
      "enabled": true,
      "category": "handoff",
      "labels": ["123"],
      "effective_time": "2023-04-07 12:52:50+0800",
      "end_time": "",
      "update_user": "admin",
      "update_time": "2023-09-08 17:54:31+0800",
      "create_user": "admin",
      "create_time": "2023-04-07 12:52:50+0800",
      "user_groups": [1, 2],
      "user_groups_count": 2,
      "delete_allowed": false,
      "edit_allowed": true
    }
  ],
  "request_id": "6b439ff5729b4e15b4b94b138b5f0fc1"
}
```
