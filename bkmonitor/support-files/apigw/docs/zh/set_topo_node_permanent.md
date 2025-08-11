### 功能描述

设置拓扑节点的永久保存状态

#### 接口参数

| 字段名     | 类型   | 必选 | 描述         |
| ---------- | ------ | ---- | ------------ |
| bk_biz_id  | Int    | 是   | 业务ID       |
| app_name   | String | 是   | 应用名称     |
| topo_key   | String | 是   | 拓扑节点Key  |
| is_permanent | Bool | 是   | 是否永久保存 |

#### 示例数据

```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
    "bk_biz_id": 123,
    "app_name": "my_app",
    "topo_key": "service1",
    "is_permanent": true
}
```

### 响应参数

| 字段名  | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | Bool   | 请求是否成功 |
| code    | Int    | 返回的状态码 |
| message | String | 描述信息     |
| data    | Null   | 空           |

#### 示例数据

```json
{
    "message": "OK",
    "code": 200,
    "data": null,
    "result": true
}
```