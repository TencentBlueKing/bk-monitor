### 功能描述

获取拨测节点列表

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段             | 类型    | 必选 | 描述                                |
|----------------|-------|-----|-----------------------------------|
| bk_biz_id      | int   | 是  | 业务ID                              |
| bk_host_id     | int   | 是  | 主机ID                              |
| is_common      | bool  | 否  | 是否为公共节点,默认false                   |
| name           | str   | 是  | 节点名称                              |
| plat_id        | int   | 是  | 云区域ID                             |
| ip_type        | int   | 否  | IP类型,4代表IPv4,6代表IPv6,默认为4,0代表全部        |

#### 示例数据

```json
{
    "bk_biz_id": 2,
    "name": "测试节点"
}
```

### 响应参数

| 字段         | 类型  | 描述 |
|:-----------|-----|----|
| bk_biz_id      | int   | 是  | 业务ID                              |
| location       | dict  | 否  | 地理位置信息,包含country(国家)和city(城市)字段   |
| carrieroperator| str   | 否  | 运营商,如: 电信、联通、移动，可自定义                |
| bk_host_id     | int   | 是  | 主机ID                              |
| is_common      | bool  | 否  | 是否为公共节点,默认false                   |
| name           | str   | 是  | 节点名称                              |
| plat_id        | int   | 是  | 云区域ID                             |
| ip_type        | int   | 否  | IP类型,4代表IPv4,6代表IPv6,默认为4,0代表全部        |
| status         | string   | 拨测节点状态, 0: 运行中, -1: 异常, 2: 需要升级, -2: 失效(找不到对应主机) |
| version        | string | 拨测节点采集器版本 |
| task_num       | int    | 拨测节点任务数量 |
| gse_status     | string | 拨测节点GSE状态, 0: 运行中, -1: 异常, 2: 需要升级, -2: 失效(找不到对应主机) |

#### 示例数据
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "id": 10255,
            "bk_biz_id": 2,
            "name": "测试节点",
            "ip": "127.0.0.1",
            "bk_host_id": 30065456,
            "bk_cloud_id": 30000585,
            "ip_type": 4,
            "country": "中国",
            "province": "天津",
            "carrieroperator": "全球",
            "task_num": 0,
            "is_common": false,
            "gse_status": "0",
            "status": "0",
            "version": "3.56.2735"
        }
    ]
}
```