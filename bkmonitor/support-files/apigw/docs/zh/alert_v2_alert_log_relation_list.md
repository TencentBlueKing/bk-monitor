### 功能描述

【告警V2】告警关联日志列表查询

### 请求参数

| 字段       | 类型  | 必选 | 描述   |
|----------|-----|----|------|
| alert_id | str | 是  | 告警ID |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2"
}
```

### 响应参数

| 字段      | 类型     | 描述       |
|---------|--------|----------|
| result  | bool   | 请求是否成功   |
| code    | int    | 返回的状态码   |
| message | string | 描述信息     |
| data    | list   | 日志检索配置列表 |

#### data 元素字段说明

| 字段                 | 类型         | 必选 | 描述                      |
|--------------------|------------|----|-------------------------|
| index_set_id       | int        | 是  | 索引集ID                   |
| index_set_name     | string     | 是  | 索引集名称                   |
| scenario_id        | string     | 是  | 场景ID（log/bcs/es等）       |
| scenario_name      | string     | 是  | 场景名称                    |
| storage_cluster_id | int        | 是  | 存储集群ID                  |
| bk_biz_id          | int        | 是  | 业务ID                    |
| time_field         | string     | 是  | 时间字段                    |
| indices            | list[dict] | 是  | 索引列表                    |
| addition           | list[dict] | 是  | 日志查询过滤条件列表，用于精确匹配告警相关日志 |
| keyword            | string     | 否  | 查询关键字（仅日志类告警包含此字段）      |
| tags               | list[dict] | 否  | 索引集标签列表                 |

#### indices 元素字段说明

| 字段              | 类型     | 必选 | 描述    |
|-----------------|--------|----|-------|
| index_name      | string | 是  | 索引名称  |
| result_table_id | string | 是  | 结果表ID |
| time_field      | string | 是  | 时间字段  |

#### addition 元素字段说明

| 字段       | 类型     | 必选 | 描述                               |
|----------|--------|----|----------------------------------|
| field    | string | 是  | 过滤字段名                            |
| operator | string | 是  | 操作符（=、!=、contains、not contains等） |
| value    | list   | 是  | 过滤值列表                            |

#### tags 元素字段说明

| 字段     | 类型     | 必选 | 描述   |
|--------|--------|----|------|
| name   | string | 是  | 标签名称 |
| color  | string | 是  | 标签颜色 |
| tag_id | int    | 否  | 标签ID |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "index_set_id": 1001,
            "index_set_name": "应用日志",
            "scenario_id": "log",
            "scenario_name": "日志采集",
            "storage_cluster_id": 1,
            "bk_biz_id": 2,
            "time_field": "dtEventTimeStamp",
            "indices": [
                {
                    "index_name": "2_bklog_app_log",
                    "result_table_id": "2_bklog.app_log",
                    "time_field": "dtEventTimeStamp"
                }
            ],
            "addition": [
                {
                    "field": "serverIp",
                    "operator": "=",
                    "value": ["127.0.0.1"]
                },
                {
                    "field": "__ext.io_kubernetes_pod_namespace",
                    "operator": "=",
                    "value": ["default"]
                }
            ],
            "keyword": "",
            "tags": [
                {
                    "name": "数据指纹",
                    "color": "green",
                    "tag_id": 1
                }
            ]
        },
        {
            "index_set_id": 1002,
            "index_set_name": "容器标准输出",
            "scenario_id": "bcs",
            "scenario_name": "容器日志",
            "storage_cluster_id": 1,
            "bk_biz_id": 2,
            "time_field": "dtEventTimeStamp",
            "indices": [
                {
                    "index_name": "2_bklog_bcs_stdout",
                    "result_table_id": "2_bklog.bcs_stdout",
                    "time_field": "dtEventTimeStamp"
                }
            ],
            "addition": [
                {
                    "field": "__ext.io_kubernetes_pod",
                    "operator": "=",
                    "value": ["nginx-deployment-7d64c8f5d9-abc12"]
                }
            ]
        }
    ]
}
```

### 说明

- 该接口根据告警类型返回与告警关联的日志平台索引集配置
- 返回的索引集信息来自日志平台的索引集列表 API
- `addition` 字段包含根据告警维度、策略过滤条件、K8S 资源信息等自动生成的日志查询过滤条件，用于精确匹配告警相关日志
- `keyword` 字段仅在日志类告警中存在，包含策略配置的查询关键字
- 可用于前端跳转到日志平台进行日志检索
- 如果告警没有关联的日志配置，返回空列表
- 不同类型的告警（主机、K8S、APM、日志类）会通过不同的关联逻辑查找相关的日志索引集
