### 功能描述

删除一个事件分组
给定一个事件分组ID，删除之


#### 接口参数

| 字段             | 类型     | 必选 | 描述     |
|----------------|--------|----|--------|
| event_group_id | int    | 是  | 事件分组ID |
| operator       | string | 是  | 操作者    |

#### 请求示例

```json
{
  "bk_app_code": "xxx",
  "bk_app_secret": "xxxxx",
  "bk_token": "xxxx",
  "event_group_id": 123,
  "operator": "admin"
}
```

### 返回结果

| 字段         | 类型     | 描述     |
|------------|--------|--------|
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息   |
| data       | dict   | 数据     |
| request_id | string | 请求ID   |

#### 结果示例

```json
{
  "message": "OK",
  "code": 200,
  "data": {},
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```
