### 功能描述

删除监控策略以及会删除相关联的屏蔽


#### 接口参数

| 字段        | 类型          | 必选  | 描述     |
| --------- | ----------- | --- | ------ |
| bk_biz_id | int         | 是   | 业务 ID  |
| id        | int         | 否   | 策略 ID   |
| ids       | List\[int\] | 否   | 策略 ID 列表 |

`id` 和 `ids` 必须要有其中一个

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "id": 64414
}
```

### 返回结果

| 字段      | 类型          | 描述       |
| ------- | ----------- | -------- |
| result  | bool        | 请求是否成功   |
| code    | int         | 返回的状态码   |
| message | string      | 描述信息     |
| data    | List\[int\] | 策略 ID 列表 |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [64414]
}
```
