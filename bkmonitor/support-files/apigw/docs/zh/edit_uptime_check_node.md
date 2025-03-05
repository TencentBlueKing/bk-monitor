### 功能描述

编辑拨测节点


#### 接口参数

| 字段             | 类型    | 必选 | 描述                                |
|----------------|-------|-----|-----------------------------------|
| node_id        | int   | 是  | 拨测节点ID                              |
| bk_biz_id      | int   | 是  | 业务ID                              |
| location       | dict  | 否  | 地理位置信息,包含country(国家)和city(城市)字段   |
| carrieroperator| str   | 否  | 运营商,如: 电信、联通、移动，可自定义                |
| bk_host_id     | int   | 是  | 主机ID                              |
| is_common      | bool  | 否  | 是否为公共节点,默认false                   |
| name           | str   | 是  | 节点名称                              |
| plat_id        | int   | 是  | 云区域ID                             |
| ip_type        | int   | 否  | IP类型,4代表IPv4,6代表IPv6,默认为4,0代表全部        |

#### 示例数据

```json
{
    "node_id": 10255,
    "location": {
        "country": "中国",
        "city": "天津"
    },
    "bk_biz_id": 2,
    "carrieroperator": "全球",
    "bk_host_id": 30065456,
    "is_common": false,
    "name": "测试节点",
    "plat_id": 30000585,
    "ip_type": 4
}
```

### 响应参数

| 字段         | 类型  | 描述 |
|:-----------|-----|----|
| id         | int   | 拨测节点ID |

#### 示例数据
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": 10255,
        "location": {
            "country": "中国",
            "city": "天津"
        },
        "carrieroperator": "全球",
        "ip": "",
        "bk_cloud_id": 30000585,
        "create_time": "2024-12-26 17:43:35+0800",
        "create_user": "admin",
        "update_time": "2024-12-26 17:43:35+0800",
        "update_user": "admin",
        "is_deleted": false,
        "bk_biz_id": 2,
        "is_common": false,
        "ip_type": 4,
        "name": "测试节点",
        "bk_host_id": 30065456
    }
}
```