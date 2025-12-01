### 功能描述
获取自定义上报的proxy主机信息

### 请求参数

| 字段名 | 类型 | 是否必选 | 描述 |
|--------|------|----------|------|
| bk_biz_id | int | 是 | 业务ID |

### 请求参数示例

```json
{
  "bk_biz_id": 2
}
```

### 响应参数

| 字段 | 类型   | 描述 |
|------|------|------|
| result | bool | 请求是否成功 |
| code | int  | 返回的状态码 |
| message | str  | 描述信息 |
| data | list    | proxy主机列表 |

#### data

| 字段 | 类型 | 描述 |
|------|------|------|
| ip | string | IP地址 |
| bk_cloud_id | int | 云区域ID |
| port | int | 端口号 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "ip": "127.0.0.1",
      "bk_cloud_id": 0,
      "port": 3366
    },
    {
      "ip": "127.0.0.1",
      "bk_cloud_id": 1,
      "port": 7788
    }
  ]
}
```