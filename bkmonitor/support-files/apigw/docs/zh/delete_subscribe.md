### 功能描述

删除/取消策略订阅

#### 请求方法

POST

#### 请求路径

`/app/subscribe/delete/`

#### 接口参数

| 字段 | 类型 | 必须 | 描述   |
|----|----|----|------|
| id | int | 是  | 订阅ID |
| bk_biz_id  | int   | 是  | 业务ID   |

#### 请求示例

```json
{ "id": 1, "bk_biz_id":  2}
```

### 响应参数

| 字段       | 类型   | 描述         |
|----------|------|------------|
| result   | bool | 请求是否成功     |
| code     | int  | 返回的状态码     |
| message  | string | 描述信息       |
| data     | bool | 操作是否成功      |
| request_id | string | 请求ID       |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": true,
  "request_id": "xxxxxxxxxx"
}
```


