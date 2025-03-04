### 功能描述

启停采集配置


#### 接口参数

| 字段        | 类型  | 必选  | 描述                           |
| --------- | --- | --- | ---------------------------- |
| bk_biz_id | int | 是   | 业务 ID                         |
| id        | int | 是   | 采集配置 ID                       |
| action    | str | 是   | 启停配置 \["enable", "disable"\] |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "id": 280,
  "action": "enable"
}
```

### 返回结果

| 字段      | 类型     | 描述     |
| ------- | ------ | ------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | str | 描述信息   |
| data    | str    | 启停结果   |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": "success"
}
```
