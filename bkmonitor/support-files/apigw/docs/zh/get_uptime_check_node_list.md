### 功能描述

获取拨测节点列表

### 请求参数

`查询字符串参数`

| 字段             | 类型    | 必选 | 描述                                |
|----------------|-------|-----|-----------------------------------|
| bk_biz_id      | int   | 否  | 业务ID,用于过滤指定业务的节点                              |
| bk_host_id     | int   | 否  | 主机ID,用于过滤指定主机的节点                              |
| is_common      | bool  | 否  | 是否为公共节点,用于过滤公共节点或业务节点                   |
| name           | str   | 否  | 节点名称,用于过滤指定名称的节点                              |
| plat_id        | int   | 否  | 云区域ID,用于过滤指定云区域的节点                             |
| ip_type        | int   | 否  | IP类型,4代表IPv4,6代表IPv6,0代表全部,用于过滤指定IP类型的节点        |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "name": "测试节点"
}
```

### 响应参数

| 字段      | 类型         | 描述     |
|---------|------------|--------|
| result  | bool       | 请求是否成功 |
| code    | int        | 返回的状态码 |
| message | str        | 描述信息   |
| data    | list[dict] | 数据     |

#### data

| 字段              | 类型     | 描述                                                                |
|-----------------|--------|-------------------------------------------------------------------|
| id              | int    | 拨测节点ID                                                            |
| bk_biz_id       | int    | 业务ID                                                              |
| name            | str    | 节点名称                                                              |
| ip              | str    | 节点IP地址或主机显示名称                                                     |
| bk_host_id      | int    | 主机ID                                                              |
| plat_id         | int    | 云区域ID                                                             |
| ip_type         | int    | IP类型,4代表IPv4,6代表IPv6,0代表全部                                        |
| country         | str    | 国家                                                                |
| province        | str    | 省份/城市                                                             |
| carrieroperator | str    | 运营商,如: 电信、联通、移动等                                                  |
| task_num        | int    | 该节点关联的拨测任务数量                                                      |
| is_common       | bool   | 是否为公共节点                                                           |
| gse_status      | string | 拨测节点GSE状态, "0": 运行中, "-1": 异常, "2": 需要升级, "-2": 失效(找不到对应主机)      |
| status          | string | 拨测节点状态, "0": 运行中, "-1": 异常, "2": 需要升级, "-2": 失效(找不到对应主机)         |
| version         | string | 拨测节点采集器版本                                                         |

### 响应参数示例
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