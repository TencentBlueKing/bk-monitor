## 功能描述

更新索引集，支持计算平台（`scenario_id=bkdata`）与第三方 Elasticsearch（`scenario_id=es`）两类接入场景。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段         | 类型 | 必选 | 描述      |
| ------------ | ---- | ---- | --------- |
| index_set_id | int  | 是   | 索引集 ID |

### 参数列表

| 字段               | 类型   | 必选     | 描述                                                       |
| ------------------ | ------ | -------- | ---------------------------------------------------------- |
| index_set_name     | string | 是       | 索引集名称                                                 |
| space_uid          | string | 是       | 空间唯一标识                                               |
| scenario_id        | string | 是       | 接入场景，`bkdata` 或 `es`                                 |
| storage_cluster_id | int    | 条件必选 | 第三方 ES 场景（`scenario_id=es`）必填，指定存储集群 ID    |
| indexes            | list   | 是       | 索引列表，不能为空                                         |
| indexes[].result_table_id | string | 是 | 结果表或物理索引标识                                       |
| indexes[].bk_biz_id | int   | 否       | 索引所属业务 ID                                            |
| indexes[].time_field | string | 否     | 时间字段                                                   |
| category_id        | string | 否       | 数据分类，默认 `other_rt`                                  |
| target_fields      | list   | 否       | 上下文目标字段                                             |
| sort_fields        | list   | 否       | 上下文排序字段                                             |

## 请求参数示例

```json
{
  "index_set_name": "应用运行日志",
  "space_uid": "bkcc__2",
  "scenario_id": "bkdata",
  "indexes": [
    {
      "bk_biz_id": 2,
      "result_table_id": "2_bklog.app",
      "time_field": "dtEventTimeStamp"
    }
  ]
}
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": {
        "index_set_id": 27,
        "index_set_name": "应用运行日志",
        "space_uid": "bkcc__2",
        "scenario_id": "bkdata",
        "category_id": "other_rt",
        "indexes": [
            {
                "index_id": 32,
                "index_set_id": 27,
                "bk_biz_id": 2,
                "result_table_id": "2_bklog.app",
                "time_field": "dtEventTimeStamp",
                "apply_status": "normal",
                "apply_status_name": "正常"
            }
        ],
        "is_active": true,
        "updated_by": "xxx",
        "updated_at": "2026-07-01 21:03:33+0800"
    }
}
```
