### 功能描述

日志数据查询

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段                    | 类型   | 必选 | 描述    |
|-----------------------|------|----|-------|
| data_format           | str  | 否  | 数据格式  |
| bk_biz_id             | int  | 是  | 业务ID  |
| data_source_label     | str  | 是  | 数据来源  |
| data_type_label       | str  | 是  | 数据类型  |
| query_string          | str  | 否  | 查询字符串 |
| index_set_id          | str  | 否  | 索引集ID |
| alert_name            | str  | 否  | 告警名称  |
| bkmonitor_strategy_id | str  | 否  | 策略ID  |
| result_table_id       | str  | 否  | 结果表ID |
| where                 | list | 否  | 过滤条件  |
| filter_dict           | dict | 否  | 过滤字典  |
| start_time            | int  | 否  | 开始时间  |
| end_time              | int  | 否  | 结束时间  |
| limit                 | int  | 否  | 查询条数  |
| offset                | int  | 否  | 查询偏移  |

#### where

| 字段     | 类型        | 必选 | 描述       |
|--------|-----------|----|----------|
| key    | str       | 是  | 条件的key   |
| method | str       | 是  | 方法       |
| value  | list[str] | 是  | 条件的value |

#### 请求示例

```json
{
  "data_source_label": "xx_xx_search",
  "data_type_label": "log",
  "end_time": 1740034724,
  "start_time": 1740028800,
  "limit": 20,
  "offset": 0,
  "query_string": "\"MUST_SEND_ALARM\"",
  "index_set_id": 53,
  "result_table_id": "7_bklog.cmdb_prod",
  "where": [
    {
      "key": "path",
      "method": "eq",
      "value": [
        "/data/xxx/logs/cmdb/xx.cmdb-sync-1.xxxx.log.INFO.20250220-132529.30676"
      ]
    },
    {
      "condition": "and",
      "key": "serverIp",
      "method": "eq",
      "value": [
        "127.0.0.1"
      ]
    }
  ],
  "filter_dict": {},
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 结果     |

#### data

| 字段            | 类型  | 描述   |
|---------------|-----|------|
| time          | int | 时间   |
| event.content | str | 事件内容 |

#### 响应示例

```json
{
  "result": true,
  "data": [
    {
      "time": 1740030797,
      "event.content": "E0220 13:53:14.966602   30676 shipper/ieg_aync_cmpy_host_relation.go:275] \"MUST_SEND_ALARM\", retry rearrange host relation failed for hosts [{\"bk_host_id\":3225988,\"unix\":0,\"rid\":\"cc0000curc6im1f7nb8m0rlaf0-cc0000curc6ie1f7nb8m0rl14g-cc0000curc6ie1f7nb8m0rknpg-cc0000curc6i61f7nb8m0rkef0-67b54acbc3e7674b3c47dce3-1739934411-26\"}], re-push to queue, rid: \"cc0000curc6im1fxxx8m0rlaf0\""
    },
    {
      "time": 1740030797,
      "event.content": "E0220 13:53:15.540988   30676 shipper/ieg_aync_cmpy_host_relation.go:275] \"MUST_SEND_ALARM\", retry rearrange host relation failed for hosts [{\"bk_host_id\":3225988,\"unix\":0,\"rid\":\"cc0000curc6im1f7nb8m0rljpg-cc0000curc6im1f7nb8m0rlaf0-cc0000curc6ie1f7nb8m0rl14g-cc0000curc6ie1f7nb8m0rknpg-67b54acbc3e7674b3c47dce3-1739934411-26\"}], re-push to queue, rid: \"cc0000curc6im1fxxx8m0rlaf0\""
    },
    {
      "time": 1740030797,
      "event.content": "E0220 13:53:16.094295   30676 shipper/ieg_aync_cmpy_host_relation.go:275] \"MUST_SEND_ALARM\", retry rearrange host relation failed for hosts [{\"bk_host_id\":3225988,\"unix\":0,\"rid\":\"cc0000curc6iu1f7nb8m0rlt40-cc0000curc6im1f7nb8m0rljpg-cc0000curc6im1f7nb8m0rlaf0-cc0000curc6ie1f7nb8m0rl14g-67b54acbc3e7674b3c47dce3-1739934411-26\"}], re-push to queue, rid: \"cc0000curc6im1fxxx8m0rlaf0\""
    }
  ],
  "meta": {
    "total": 9223
  },
  "code": 200,
  "message": "OK"
}
```
