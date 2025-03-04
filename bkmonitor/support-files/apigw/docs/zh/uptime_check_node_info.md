### 功能描述

获取指定拨测节点信息


#### 接口参数

`路径参数`

| 字段      | 类型  | 必选 | 描述     |
|---------|-----|----|--------|
| node_id | int | 是  | 拨测节点ID |

#### 示例数据

`路径参数`

```json
{
  "node_id": "10017"
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

#### data

| 字段              | 类型        | 描述       |
|-----------------|-----------|----------|
| bk_biz_id       | int       | 业务ID     |
| id              | int       | 拨测节点ID   |
| is_common       | bool      | 是否为通用节点  |
| biz_scope       | list[int] | 指定业务可见范围 |
| ip_type         | int       | IP类型     |
| name            | str       | 节点名称     |
| ip              | str       | IP地址     |
| bk_host_id      | int       | 主机ID     |
| location        | dict      | 地区       |
| carrieroperator | str       | 外网运营商    |
| bk_cloud_id     | int       | 云区域ID    |
| bk_host_id      | int       | 主机ID     |
| create_time     | str       | 创建时间     |
| create_user     | str       | 创建者      |
| update_time     | str       | 更新时间     |
| update_user     | str       | 更新者      |
| is_deleted      | bool      | 是否已删除    |

#### data.location

| 字段      | 类型  | 描述  |
|---------|-----|-----|
| country | str | 国家名 |
| city    | str | 城市名 |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 10017,
    "location": {
      "country": "中国",
      "city": "河北"
    },
    "carrieroperator": "移动",
    "ip": "",
    "bk_cloud_id": 0,
    "create_time": "2025-01-20 16:54:39+0800",
    "create_user": "admin",
    "update_time": "2025-01-20 16:54:39+0800",
    "update_user": "admin",
    "is_deleted": false,
    "bk_biz_id": 2,
    "is_common": false,
    "biz_scope": "[]",
    "ip_type": 4,
    "name": "node1",
    "bk_host_id": 185
  }
}
```
