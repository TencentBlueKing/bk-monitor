# 功能描述

采集项列表（分页）

## 请求参数

### 鉴权头

| 参数名称   |  参数类型  |  必须  |     参数说明     |
| ------------ | ------------ | ------ | ---------------- |
|   app_code   |   string     |   是   |  蓝鲸应用ID    |
|   app_secret |   string     |   是   | 蓝鲸应用秘钥 |
|   bk_username |   string     |   是  |  用户名称 |


### 参数列表

| 字段      |  类型      | 必选   |  描述      |
|-----------|------------|--------|------------|
| page         |  int    | 是     | 页数 |
| pagesize  |  int   | 是     | 每页数量 |
| bk_biz_id  |  int   | 否     | 业务ID |
| space_uid | string | 否 | 空间唯一标识，与bk_biz_id二选一 |
| keyword  |  string   | 否     | 搜索关键字，模糊匹配采集项名称、结果表 ID、业务 ID |
| collector_id_list  |  string   | 否     | 采集项ID过滤，用英文逗号分隔："1,2,3" |
| bk_data_id  |  int   | 否     | bk_data_id过滤 |
| have_data_id  |  string   | 否     | 仅返回存在bk_data_id的采集项，传入任意非空值即生效 |
| bkdata  |  string   | 否     | 仅返回默认清洗（文本清洗）采集项，传入任意非空值且特性开关scenario_bkdata为off时生效 |
| not_custom  |  string   | 否     | 是否过滤掉自定义采集类型的采集项（自定义上报、客户端日志），传入任意非空值即生效 |
| have_table_id  |  string   | 否     | 仅返回存在table_id的采集项，传入任意非空值即生效 |
| ignore_display_config  |  string   | 否     | 是否忽略可见配置，传入任意非空值即生效 |

## 调用示例

```python
import json
import requests

# 目标URL，实际调用地址参考文档
url = "https://example.com/list_databus_collectors/"

# 构造鉴权头
headers = {
    "X-Bkapi-Authorization": json.dumps({
        "bk_app_code": "your app code",
        "bk_app_secret": "your app secret",
        "bk_username": "your name"
    })
}

# 构造请求参数
params = {
    "page": 1,
    "pagesize": 10,
}

# 发起请求
response = requests.get(url, headers=headers, params=params)

# 输出返回内容
print(response.json())
```


## 参数示例

### Case 1: 基本分页查询

查询第1页，每页10条数据

```json
{
    "page": 1,
    "pagesize": 10
}
```

### Case 2: 按业务ID过滤

查询指定业务下的采集项

```json
{
    "page": 1,
    "pagesize": 10,
    "bk_biz_id": 2
}
```

### Case 3: 按空间唯一标识过滤

通过space_uid查询指定空间下的采集项

```json
{
    "page": 1,
    "pagesize": 10,
    "space_uid": "bkcc__2"
}
```

### Case 4: 使用关键字搜索

搜索关键字，模糊匹配采集项名称、结果表 ID、业务 ID

```json
{
    "page": 1,
    "pagesize": 10,
    "keyword": "test"
}
```

### Case 5: 按采集项ID过滤

通过采集项ID列表过滤指定采集项

```json
{
    "page": 1,
    "pagesize": 10,
    "collector_id_list": "1,2,3"
}
```

### Case 6: 按bk_data_id过滤

通过指定bk_data_id查找对应采集项

```json
{
    "bk_biz_id": 2,
    "bk_data_id": 525452
}
```

### Case 7: 仅返回存在bk_data_id的采集项

仅返回存在bk_data_id的采集项

```json
{
    "page": 1,
    "pagesize": 10,
    "have_data_id": 1
}
```

### Case 8: 仅显示BK-Data数据

当特性开关scenario_bkdata为off时，并且请求参数bkdata传入任意非空值，仅返回BK-Data类型的采集项

```json
{
    "page": 1,
    "pagesize": 10,
    "bkdata": 1
}
```

### Case 9: 过滤掉自定义采集类型

排除自定义上报和客户端日志类型的采集项

```json
{
    "page": 1,
    "pagesize": 10,
    "not_custom": 1
}
```

### Case 10: 仅返回存在table_id的采集项

仅返回存在table_id的采集项

```json
{
    "page": 1,
    "pagesize": 10,
    "have_table_id": 1
}
```

### Case 11: 忽略可见配置

返回全部数据，不受可见配置限制

```json
{
    "page": 1,
    "pagesize": 10,
    "ignore_display_config": 1
}
```


## 返回结果示例

```json
{
    "result": true,
    "data": {
        "total": 1,
        "list": [
            {
                "collector_config_id": 66666708,
                "collector_scenario_name": "行日志文件",
                "category_name": "其他",
                "target_nodes": [
                    {
                        "bk_inst_id": 190,
                        "bk_obj_id": "module"
                    }
                ],
                "task_id_list": [
                    "17056460",
                    "17056564"
                ],
                "target_subscription_diff": {},
                "create_clean_able": true,
                "bkdata_index_set_ids": [],
                "created_at": "2026-06-05 10:41:36+0800",
                "created_by": "admin",
                "updated_at": "2026-06-05 10:45:24+0800",
                "updated_by": "admin",
                "is_deleted": false,
                "deleted_at": null,
                "deleted_by": null,
                "bk_biz_id": 2,
                "bkdata_biz_id": null,
                "collector_config_name": "test_es_version_is_none_01",
                "collector_plugin_id": null,
                "bk_app_code": "bk_log_search",
                "collector_scenario_id": "row",
                "custom_type": "log",
                "category_id": "other_rt",
                "target_object_type": "HOST",
                "target_node_type": "TOPO",
                "description": "test_es_version_is_none_01",
                "is_active": true,
                "data_link_id": 1,
                "bk_data_id": 1576607,
                "bk_data_name": null,
                "table_id": "test_es_version_is_none_01",
                "bkbase_table_id": null,
                "processing_id": null,
                "etl_processor": "transfer",
                "etl_config": "bk_log_text",
                "subscription_id": 13420,
                "bkdata_data_id": null,
                "index_set_id": 66666713,
                "data_encoding": "UTF-8",
                "params": "{'paths': ['/tmp/bkc.log'], 'exclude_files': [], 'conditions': {'type': 'none', 'match_content': None, 'separator': None}, 'tail_files': True, 'ignore_older': 86400, 'max_bytes': 204800, 'winlog_name': [], 'winlog_level': [], 'winlog_event_id': [], 'redis_hosts': [], 'extra_labels': [], 'syslog_conditions': [], 'kafka_hosts': [], 'kafka_ssl_params': {}, 'kafka_topics': [], 'kafka_group_id': '', 'kafka_initial_offset': 'newest', 'encoding': 'UTF-8', 'run_task': True}",
                "itsm_ticket_sn": null,
                "itsm_ticket_status": "not_apply",
                "can_use_independent_es_cluster": true,
                "collector_package_count": 10,
                "collector_output_format": null,
                "collector_config_overlay": null,
                "storage_shards_nums": 1,
                "storage_shards_size": 30,
                "storage_replies": 0,
                "bkdata_data_id_sync_times": 0,
                "collector_config_name_en": "test_es_version_is_none_01",
                "environment": "linux",
                "bcs_cluster_id": null,
                "extra_labels": [],
                "add_pod_label": false,
                "add_pod_annotation": false,
                "yaml_config_enabled": false,
                "yaml_config": "",
                "rule_id": 0,
                "is_display": true,
                "log_group_id": null,
                "is_nanos": false,
                "enable_v4": true,
                "storage_cluster_type": "elasticsearch",
                "storage_cluster_id": 3,
                "storage_cluster_name": "es7_cluster",
                "storage_display_name": "es集群7",
                "retention": 1,
                "table_id_prefix": "2_bklog_",
                "custom_name": "容器日志上报",
                "is_search": true,
                "tags": [],
                "permission": {
                    "search_log_v2": true,
                    "view_collection_v2": true,
                    "manage_collection_v2": true
                }
            }
        ]
    },
    "code": 0,
    "message": ""
}
```