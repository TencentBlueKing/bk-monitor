### 功能描述

查询存储集群的详细信息

### 请求参数

| 字段         | 类型  | 必选 | 描述              |
|------------|-----|----|-----------------|
| cluster_id | str | 是  | 集群 ID           |
| page_size  | int | 否  | 每页的条数，默认为 10    |
| page       | int | 否  | 页数，最小值为 1，默认为 1 |

### 请求参数示例

```json
{
    "cluster_id": "1"
}
```

### 响应参数

| 字段      | 类型         | 描述                                 |
|---------|------------|------------------------------------|
| result  | bool       | 请求是否成功                             |
| code    | int        | 返回的状态码                             |
| message | str        | 描述信息                               |
| data    | list[dict] | 集群详情列表，每个元素代表一个节点信息，字段因集群类型不同而有所差异 |

#### data 元素字段说明（Kafka 集群）

| 字段          | 类型  | 描述             |
|-------------|-----|----------------|
| host        | str | 节点主机地址         |
| port        | int | 节点端口           |
| topic_count | int | 该节点上的 Topic 数量 |
| version     | str | 集群版本           |
| schema      | str | 访问协议           |

#### data 元素字段说明（ES / InfluxDB / VM 集群）

| 字段      | 类型  | 描述     |
|---------|-----|--------|
| host    | str | 集群主机地址 |
| port    | int | 集群端口   |
| version | str | 集群版本   |
| schema  | str | 访问协议   |
| status  | str | 集群状态   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "host": "es.example.com",
            "port": 9200,
            "version": "7.10.0",
            "schema": "http",
            "status": "running"
        }
    ]
}
```
