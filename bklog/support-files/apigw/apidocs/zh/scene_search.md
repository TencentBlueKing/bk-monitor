## 功能描述

场景化日志检索接口

## 请求参数

### 鉴权头
| 参数名称 | 参数类型 | 必须 | 参数说明 |
|---|---|---|---|
| app_code | string | 是 | 蓝鲸应用ID |
| app_secret | string | 是 | 蓝鲸应用秘钥 |
| bk_username | string | 是 | 用户名称 |


### 参数列表
| 字段 | 类型 | 必选 | 描述 |
|---|---|---|---|
| space_uid | string | 是 | 空间UID,例如`bkcc__2` |
| bk_biz_id | int | 否 | 业务ID,不传时后端会尝试从`space_uid`解析 |
| table_id_conditions | list | 是 | 结果表路由条件,二维数组,外层 OR,内层 AND,详见下方说明 |
| scene_filter_values | list | 否 | 场景维度过滤条件,格式同`addition`,会合并到查询过滤条件中 |
| keyword | string | 否 | 查询字符串,默认为`*` |
| addition | list | 否 | 结构化过滤条件 |
| start_time | string | 是 | 查询开始时间,支持`YYYY-MM-DD HH:mm:ss`、秒级或毫秒级时间戳 |
| end_time | string | 是 | 查询结束时间,支持`YYYY-MM-DD HH:mm:ss`、秒级或毫秒级时间戳 |
| begin | int | 否 | 偏移量,默认0 |
| size | int | 否 | 最大返回结果条数,默认50,最大10000;超过10000时按10000处理 |
| sort_list | list | 否 | 结果排序字段列表,每项为`[字段名, asc/desc]`,默认按`dtEventTimeStamp`倒序 |
| is_desensitize | boolean | 否 | 是否执行脱敏,默认true |


#### table_id_conditions
场景化检索使用`table_id_conditions`路由匹配结果表,结构为二维数组:

- 外层数组表示 OR 关系
- 内层数组表示 AND 关系
- 每个条件元素结构如下

| 字段 | 类型 | 必选 | 描述 |
|---|---|---|---|
| field_name | string | 是 | 标签字段名,例如`scene`、`cluster_id`、`stream` |
| value | list | 是 | 匹配值列表 |
| op | string | 否 | 操作符,支持`eq`、`ne`、`req`、`nreq`,默认`eq` |


#### addition / scene_filter_values
| 字段 | 类型 | 必选 | 描述 |
|---|---|---|---|
| field | string | 是 | 筛选字段名称 |
| operator | string | 是 | 比较运算符,例如`is`、`is one of`、`is not`、`is not one of` |
| value | string/list | 是 | 筛选值 |


### 补充说明
1. `scene`是场景路由分类字段,常见值包括`k8s`、`host`、`bk_paas`等,具体以场景列表接口返回为准。
2. `table_id_conditions`中的非`scene`字段用于继续缩小命中结果表范围,例如`cluster_id`、`stream`等。
3. `table_id_conditions`避免只传`scene`进行大范围查询,建议同时指定`cluster_id`、`stream`等具体场景维度,缩小命中结果表范围。


## 参数示例

### Case 1: 按场景维度路由并过滤日志内容

查询指定容器集群下,命名空间为`default`且日志级别为`WARN`或`ERROR`的数据

```json
{
    "space_uid": "bkcc__2",
    "bk_biz_id": 2,
    "table_id_conditions": [
        [
            {
                "field_name": "scene",
                "value": [
                    "k8s"
                ],
                "op": "eq"
            },
            {
                "field_name": "cluster_id",
                "value": [
                    "BCS-K8S-00000"
                ],
                "op": "eq"
            }
        ]
    ],
    "keyword": "*",
    "scene_filter_values": [
        {
            "field": "__ext.io_kubernetes_pod_namespace",
            "operator": "is",
            "value": "default"
        }
    ],
    "addition": [
        {
            "field": "level",
            "operator": "is one of",
            "value": [
                "WARN",
                "ERROR"
            ]
        }
    ],
    "start_time": "2026-06-29 10:00:00",
    "end_time": "2026-06-29 10:15:00",
    "begin": 0,
    "size": 50
}
```


## 响应参数

| 字段 | 类型 | 描述 |
|---|---|---|
| result | bool | 请求是否成功 |
| code | int | 返回的状态码 |
| message | string | 描述信息 |
| data | object | 返回日志内容 |
| request_id | string | 请求ID |


### data
| 字段 | 类型 | 描述 |
|---|---|---|
| took | int | 查询耗时 |
| total | int/object | 匹配日志总数 |
| list | list | 日志列表 |
| origin_log_list | list | 原始日志列表 |
| fields | object | 字段长度分析结果 |
| result_table_id | list | 本次命中的结果表 |


## 返回结果示例

```json
{
    "result": true,
    "data": {
        "took": 32,
        "total": 1,
        "list": [
            {
                "__data_label": "bklog_index_set_1000002",
                "_time": "1782727500000",
                "dtEventTimeStamp": "1782727500000",
                "gseIndex": 2665481,
                "iterationIndex": 12,
                "log": "request success",
                "path": "/var/lib/app/app.log",
                "__ext": {
                    "io_kubernetes_pod_namespace": "default"
                }
            }
        ],
        "origin_log_list": [
            {
                "__data_label": "bklog_index_set_1000002",
                "_time": "1782727500000",
                "dtEventTimeStamp": "1782727500000",
                "gseIndex": 2665481,
                "iterationIndex": 12,
                "log": "request success",
                "path": "/var/lib/app/app.log"
            }
        ],
        "fields": {},
        "result_table_id": [
            "2_bklog.container_stdout"
        ]
    },
    "code": 0,
    "message": "",
    "request_id": ""
}
```
