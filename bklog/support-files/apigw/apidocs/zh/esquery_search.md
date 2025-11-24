## 功能描述

日志查询接口

## 请求参数

### 鉴权头

| 参数名称        | 参数类型   | 必须 | 参数说明   |
|-------------|--------|----|--------|
| app_code    | string | 是  | 蓝鲸应用ID |
| app_secret  | string | 是  | 蓝鲸应用秘钥 |
| bk_username | string | 是  | 用户名称   |


### 参数列表

| 字段                 | 类型       | 必选 | 描述                                                                                                                            |
|--------------------|----------|----|-------------------------------------------------------------------------------------------------------------------------------|
| index_set_id       | int      | 否  | 索引集ID，非数据平台时需要传入                                                                                                              |
| indices            | string   | 否  | 索引列表，多个索引用英文逗号连接, 用于指定数据平台索引                                                                                                  |
| scenario_id        | string   | 否  | ES接入场景(原生ES：es; 日志采集：log; 数据平台：bkdata，默认为log)                                                                                 |
| storage_cluster_id | int      | 否  | 当scenario_id为es或log时候需要传入                                                                                                     |
| time_field         | string   | 否  | 时间字段（非必填，bkdata内部为dtEventTimeStamp，外部如果传入时间范围需要指定时间字段）                                                                        |
| start_time         | string   | 否  | 开始时间。格式: `2006-01-02 15:04:05`。不填默认为最近15分钟                                                                                    |
| end_time           | string   | 否  | 结束时间。格式: `2006-01-02 15:04:05`。不填默认为当前时刻                                                                                      |
| time_range         | string   | 否  | 时间范围标识符["15m", "30m", "1h", "4h", "12h", "1d", "customized"]                                                                  |
| query_string       | string   | 否  | 查询字符串。                                                                                                                        |
| filter             | []Filter | 否  | 结构化过滤条件，多个条件之间为与的关系，与 `query_string` 共同生效                                                                                     |
| start              | int      | 否  | 分页偏移量，默认为0                                                                                                                    |
| size               | int      | 否  | 分页条数，默认为10。start + size 不允许超过 10000，如需查询更多条数需使用 `search_after` 参数进行轮询                                                         |
| sort_list          | list     | 否  | 指定排序字段，列表每一项由 `字段名 + 升降序(asc/desc)` 构成   如 `[["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]]` |
| search_after       | list     | 否  | 需配合 `sort_list` 参数一并使用，需给出上一次请求的最后一条 `sort_list` 字段值，如 `[1718613905000, 19170867]`                                            |
| slice_search       | boolean  | 否  | 是否分片查询，默认为`false`                                                                                                             |
| slice_id           | int      | 否  | 指定分片                                                                                                                          |
| slice_max          | int      | 否  | 分片数量                                                                                                                          |


#### Filter

| 字段       | 类型           | 必选 | 描述         |
|----------|--------------|----|------------|
| field    | string       | 是  | 需要过滤的字段名   |
| operator | string       | 是  | 操作符，可选值见下表 |
| value    | list[string] | 是  | 需要过滤的字段值   |


#### operator

| 取值                          | 解释                                                                                                 |
|-----------------------------|----------------------------------------------------------------------------------------------------|
| `=`                         | 等于                                                                                                 |
| `!=`                        | 不等于                                                                                                |
| `=~`                        | 通配符等于，`?` 代表单字符，`*` 代表 0 或多个字符。比如 `qu?ck bro*`                                                     |
| `!=~`                       | 通配符不等于，语法规则同 `=~`                                                                                  |
| `contains match phrase`     | 短语包含，仅 `log` 等分词字段使用。比如 `"time out"`,  可匹配日志 `"request time out"`，但若单词不完整，则无法匹配结果，比如 `"quest tim"` |
| `not contains match phrase` | 短语不包含，语法规则同 `contains match phrase`                                                                |
| `>=`                        | 大于等于                                                                                               |
| `>`                         | 大于                                                                                                 |
| `<=`                        | 小于等于                                                                                               |
| `<`                         | 小于                                                                                                 |


## 调用示例

```python
import json
import requests

# 目标URL，实际调用地址参考文档
url = "https://example.com/esquery_search/"

# 构造鉴权头
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}

# 构造请求参数
data = {
    "index_set_id": 16176,
}

# 发起请求
response = requests.post(url, headers=headers, json=data)

# 输出返回内容
print(response.json())
```


## 参数示例

### Case 1: 给定时间范围

查询 2025-09-15 ，19 点到 20 点(包含) 的日志

```json
{
    "index_set_id": 16176,
    "start_time": "2025-09-15 19:00:00",
    "end_time": "2025-09-15 20:00:00"
}
```


### Case 2: 分页查询

获取第11~20条数据

```json
{
    "index_set_id": 16176,
    "start_time": "2025-09-15 19:00:00",
    "end_time": "2025-09-15 20:00:00",
    "start": 10,
    "size": 10
}
```
⚠️ start + size 不允许超过 10000，如需查询更多条数需使用 `search_after` 参数进行轮询



### Case 3: 使用查询字符串

全字段全文检索关键字 `"empty token"`

```json
{
    "index_set_id": 16176,
    "start_time": "2025-09-15 19:00:00",
    "end_time": "2025-09-15 20:00:00",
    "query_string": "\"empty token\""
}
```



### Case 4: 使用结构化过滤条件

查询日志级别 `level` 为 `"WARN"` 或 `"ERROR"` 的日志

```json
{
    "index_set_id": 16176,
    "start_time": "2025-09-15 19:00:00",
    "end_time": "2025-09-15 20:00:00",
    "filter": [
        {
            "field": "level",
            "operator": "=",
            "value": ["WARN", "ERROR"]
        }
    ]
}
```



### Case 5: 使用排序

按日志上报时间倒序进行排序

```json
{
    "index_set_id": 16176,
    "start_time": "2025-09-15 19:00:00",
    "end_time": "2025-09-15 20:00:00",
    "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]]
}
```



### Case 6: 滚动查询

适用于结果集超过1万条日志的全量拉取

⚠️ 拉取数据量不建议超过200万，否则会给存储集群带来巨大的压力

滚动查询需通过多次循环迭代查询完成，分 3 个步骤

1. 首次查询
    ```json
    {
        "index_set_id": 16176,
        "start_time": "2025-09-15 19:00:00",
        "end_time": "2025-09-15 20:00:00",
        "start": 0,
        "size": 10000,
        "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]]
    }
    ```

2. 获取查询结果，从 `hits` 列表中获取到最后一条数据的 `sort` 字段，形如 `[1757937598602,2665481,12]` ，将该值作为下一次查询的 `search_after` 参数，如下 (注意除 `search_after` 参数外，其他参数保持不变)
    ```json
    {
        "index_set_id": 16176,
        "start_time": "2025-09-15 19:00:00",
        "end_time": "2025-09-15 20:00:00",
        "start": 0,   
        "size": 10000,
        "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]],
        "search_after": [1757937598602,2665481,12]
    }
    ```

3. 重复步骤 2，直至返回的 `hits` 结果数量小于 `size`




## 返回结果示例

```json
{
    "result": true,
    "message": "查询成功",
    "data": {
        "hits": {
            "hits": [
                {
                    "_score": 2,
                    "_type": "xx",
                    "_id": "xxx",
                    "_source": {
                        "dtEventTimeStamp": 1565453112000,
                        "report_time": "2019-08-11 00:05:12",
                        "log": "xxxxxx",
                        "ip": "127.0.0.1",
                        "gseindex": 5857918,
                        "_iteration_idx": 3,
                        "path": "xxxxx"
                    },
                    "_index": "xxxxxxxx"
                },
                {
                    "_score": 2,
                    "_type": "xxxx",
                    "_id": "xxxxx",
                    "_source": {
                        "dtEventTimeStamp": 1565453113000,
                        "report_time": "2019-08-11 00:05:13",
                        "log": "xxxxxxx",
                        "ip": "127.0.0.1",
                        "gseindex": 5857921,
                        "_iteration_idx": 2,
                        "path": "xxxxxxxxx"
                    },
                    "_index": "xxxxxxx"
                }
            ],
            "total": 8429903,
            "max_score": 2
        },
        "_shards": {
            "successful": 9,
            "failed": 0,
            "total": 9
        },
        "took": 136,
        "timed_out": false
    },
    "code": 0
}
```