### 功能描述

删除采集配置

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段        | 类型  | 必选  | 描述     |
| --------- | --- | --- | ------ |
| bk_biz_id | int | 是   | 业务 ID   |
| id        | int | 是   | 采集配置 ID |

#### 请求示例

```json
{
  "id": 287,
  "bk_biz_id": 2
}
```

### 返回结果

| 字段      | 类型     | 描述     |
| ------- | ------ | ------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 数据始终为null     |

#### data 字段说明

data 字段无内容

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": null
}
```
