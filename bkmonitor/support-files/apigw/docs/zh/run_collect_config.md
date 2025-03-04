### 功能描述

主动执行部分实例或节点


#### 接口参数

| 字段        | 类型   | 必选  | 描述                 |
| --------- | ---- | --- | ------------------ |
| bk_biz_id | int  | 是   | 业务 ID              |
| id        | int  | 是   | 采集配置 ID            |
| action    | str  | 否   | 执行操作, 默认 "install" |
| scope     | dict | 否   | 事件订阅监听的范围          |

##### scope

| 字段        | 类型   | 必选  | 描述                                 |
| --------- | ---- | --- | ---------------------------------- |
| node_type | str  | 是   | 采集对象类型, 可选值 \["TOPO", "INSTANCE"\] |
| nodes     | List | 是   | 节点列表                               |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "id": 280
}
```

### 返回结果

| 字段      | 类型     | 描述     |
| ------- | ------ | ------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | str    | 执行结果   |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": "success"
}
```
