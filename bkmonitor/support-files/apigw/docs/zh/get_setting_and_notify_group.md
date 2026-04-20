### 功能描述

获取配置管理员及其业务、告警接收人及其业务

### 请求参数

无

### 请求参数示例

无

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段               | 类型   | 描述        |
|------------------|------|-----------|
| controller_group | dict | 配置管理员组信息  |
| alert_group      | dict | 告警接收人员组信息 |

#### controller_group/alert_group 字段说明

| 字段        | 类型        | 描述                             |
|-----------|-----------|--------------------------------|
| users     | list[str] | 用户名列表                          |
| users_biz | dict      | 用户对应的业务ID映射，key为用户名，value为业务ID |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "controller_group": {
      "users": ["admin", "user1", "user2"],
      "users_biz": {
        "admin": [2, 3, 5],
        "user1": [2, 3],
        "user2": [5, 7]
      }
    },
    "alert_group": {
      "users": ["user3", "user4", "user5"],
      "users_biz": {
        "user3": [2, 3],
        "user4": [5, 7],
        "user5": [2, 5, 7]
      }
    }
  }
}
```
