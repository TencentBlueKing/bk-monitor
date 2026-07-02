## 功能描述

查询日志原始数据。基于 UnifyQuery 协议，支持结构化过滤、分页与滚动查询，返回原始日志明细。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表

| 字段                 | 类型   | 必选 | 描述                                                    |
| -------------------- | ------ | ---- | ------------------------------------------------------- |
| bk_biz_id            | int    | 是   | 业务 ID                                                 |
| query_list           | list   | 是   | 查询配置列表，包含 1 个或多个数据源的查询条件           |
| order_by             | list   | 否   | 结果排序字段列表，`-` 前缀表示降序                      |
| start_time           | string | 是   | 查询开始时间戳                                          |
| end_time             | string | 是   | 查询结束时间戳                                          |
| from                 | int    | 否   | 偏移量                                                  |
| limit                | int    | 是   | 最大返回结果条数                                        |
| metric_merge         | string | 否   | 指标合并标识，用于拼接 query_list 中 reference_name 相同的查询结果 |
| result_table_options | object | 否   | 滚动查询参数，用于分页查询，包含每个数据表的分页信息    |

#### query_list

| 字段           | 类型   | 必选 | 描述                                                  |
| -------------- | ------ | ---- | ----------------------------------------------------- |
| data_source    | string | 是   | 数据源名称，传 `bklog` 即可                           |
| table_id       | string | 是   | 查询的数据表，格式固定为 `bklog_index_set_{索引集ID}` |
| query_string   | string | 否   | 查询字符串                                            |
| conditions     | object | 否   | 结构化的过滤条件                                      |
| reference_name | string | 否   | 查询引用名称，与 metric_merge 配合实现结果合并        |
| keep_columns   | list   | 否   | 需要保留的输出字段列表                                |
| collapse       | object | 否   | 折叠字段，用于按指定字段去重                          |

#### conditions

| 字段           | 类型 | 必选 | 描述                                                         |
| -------------- | ---- | ---- | ------------------------------------------------------------ |
| field_list     | list | 否   | 字段筛选条件列表，每个元素为一个具体字段的筛选规则           |
| condition_list | list | 否   | 逻辑运算符列表，长度为 `field_list.length - 1`，如 `["and", "or"]` |

#### field_list

| 字段       | 类型    | 必选 | 描述                            |
| ---------- | ------- | ---- | ------------------------------- |
| field_name | string  | 是   | 筛选字段名称（支持嵌套字段）    |
| value      | list    | 是   | 筛选值列表（多值默认“或”关系）  |
| op         | string  | 是   | 比较运算符，支持 `eq`、`ne`、`req` 等 |

#### result_table_options

滚动查询时用于传递分页信息的参数，结构为键值对形式，每个键代表一个数据表的唯一标识。

| 字段         | 类型 | 必选 | 描述                                            |
| ------------ | ---- | ---- | ----------------------------------------------- |
| from         | int  | 否   | 偏移量，通常为 0                                |
| search_after | list | 是   | 搜索游标，从上一次查询的返回结果中获取          |

### 补充说明

1. 逻辑运算符规则：`condition_list` 中的元素与 `field_list` 的条件按顺序关联，如 `field_list` 有 3 个条件，`condition_list: ["and", "or"]` 表示“(条件1 and 条件2) or 条件3”。
2. 正则匹配（`op: "req"`）：`value` 需传入正则表达式字符串，例如 `"bkm-pay-[a-z0-9]{5,10}"`。
3. 使用 `result_table_options` 时必须同时指定 `order_by` 参数；每次查询后应将返回结果中的 `result_table_options` 作为下一次请求参数继续查询；若某个键的 `from=0` 且没有 `search_after`，则该键应被剔除。

## 参数示例

### Case 1：查询给定时间范围内的数据

```json
{
    "bk_biz_id": 2,
    "query_list": [
        {
            "data_source": "bklog",
            "query_string": "*",
            "table_id": "bklog_index_set_xxxxx"
        }
    ],
    "start_time": "1766564792340",
    "end_time": "1766651192340",
    "limit": 50
}
```

### Case 2：使用查询字符串

查询日志级别 `level` 为 `"ERROR"`。

```json
{
    "bk_biz_id": 2,
    "query_list": [
        {
            "data_source": "bklog",
            "query_string": "level: ERROR",
            "table_id": "bklog_index_set_xxxx"
        }
    ],
    "start_time": "1766564792340",
    "end_time": "1766651192340",
    "limit": 50
}
```

### Case 3：使用结构化过滤条件

查询日志级别 `level` 为 `"WARN"` 或 `"ERROR"` 并且 `cluster_id = 1` 的日志。

```json
{
    "bk_biz_id": 2,
    "query_list": [
        {
            "data_source": "bklog",
            "conditions": {
                "field_list": [
                    {"field_name": "level", "op": "eq", "value": ["WARN", "ERROR"]},
                    {"field_name": "cluster_id", "op": "eq", "value": ["1"]}
                ],
                "condition_list": ["and"]
            },
            "table_id": "bklog_index_set_xxxx"
        }
    ],
    "start_time": "1766564792340",
    "end_time": "1766651192340",
    "limit": 50
}
```

### Case 4：分页查询（from + limit）

适用于数据量较小的场景，后续查询令 `from = from + limit`。

```json
{
    "bk_biz_id": 2,
    "query_list": [
        {"data_source": "bklog", "table_id": "bklog_index_set_xxxx"}
    ],
    "start_time": "1766564792340",
    "end_time": "1766651192340",
    "limit": 50,
    "from": 50
}
```

### Case 5：滚动查询（search_after）

适用于结果集超过 1 万条日志的全量拉取。

⚠️ 拉取数据量不建议超过 200 万，否则会给存储集群带来巨大的压力。

滚动查询需多次循环迭代，必须传递 `order_by` 参数并设置 `"is_search_after": true`：

1. 首次查询

```json
{
    "bk_biz_id": 2,
    "query_list": [
        {"data_source": "bklog", "table_id": "bklog_index_set_1000002"}
    ],
    "start_time": "1766654732166",
    "end_time": "1766655632167",
    "limit": 10000,
    "order_by": ["-dtEventTimeStamp"],
    "is_search_after": true
}
```

2. 将返回结果中的 `result_table_options` 作为下一次请求参数继续查询：

```json
{
    "bk_biz_id": 2,
    "query_list": [
        {"data_source": "bklog", "table_id": "bklog_index_set_xxxx"}
    ],
    "start_time": "1766564792340",
    "end_time": "1766651192340",
    "limit": 10000,
    "order_by": ["-dtEventTimeStamp"],
    "is_search_after": true,
    "result_table_options": {
        "bklog_index_set_xxxx_2_bklog_ljl_test_002.__default__|3": {
            "from": 0,
            "search_after": [1766651191000]
        }
    }
}
```

3. 重复步骤 2，直至返回的 `list` 为空。

### Case 6：折叠查询

按指定字段去重，以下例子返回每种 `level` 值对应的随机一条日志内容。

```json
{
    "bk_biz_id": 2,
    "query_list": [
        {
            "data_source": "bklog",
            "table_id": "bklog_index_set_xxxx",
            "collapse": {"field": "level"}
        }
    ],
    "start_time": "1766564792340",
    "end_time": "1766651192340",
    "limit": 50,
    "from": 0
}
```

## 返回结果示例

```json
{
    "total": 5706,
    "list": [
        {
            "__data_label": "bklog_index_set_xxxx",
            "_time": "1766655632000",
            "bk_host_id": 0,
            "cloudId": 0,
            "dtEventTimeStamp": "1766655632000",
            "gseIndex": 501517,
            "iterationIndex": 0,
            "log": "xxxxxx",
            "path": "/var/lib/xxx.log",
            "time": "1766655632000"
        }
    ],
    "done": false,
    "trace_id": "df98523a2a4f0a1d6c5780a95185f275",
    "status": null,
    "result_table_options": {
        "bklog_index_set_1000002_2_bklog_ljl_test_002.__default__|3": {
            "from": 0,
            "search_after": [1766655632000]
        }
    }
}
```
