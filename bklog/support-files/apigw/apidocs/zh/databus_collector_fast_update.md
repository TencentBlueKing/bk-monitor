## 功能描述

快速修改一个采集项，覆盖普通主机日志、Windows 日志与普通容器日志。

后端路径：`POST /api/v1/databus/collectors/{collector_config_id}/fast_update/`，`Content-Type: application/json`。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段                | 类型 | 必选 | 描述      |
| ------------------- | ---- | ---- | --------- |
| collector_config_id | int  | 是   | 采集项 ID |

### 参数列表（物理环境）

| 字段                  | 类型   | 必选 | 描述                                                       |
| --------------------- | ------ | ---- | ---------------------------------------------------------- |
| collector_config_name | string | 是   | 采集项名称                                                 |
| target_nodes          | list   | 否   | 采集目标，详见 TargetNodes                                 |
| description           | string | 否   | 描述信息                                                   |
| params                | dict   | 是   | 采集插件参数，详见 Plugin Params                          |
| etl_config            | string | 否   | 清洗类型，默认 `bk_log_text`                               |
| etl_params            | dict   | 否   | 清洗参数                                                   |
| fields                | list   | 否   | 字段配置                                                   |
| retention             | int    | 否   | 数据过期时间                                               |
| allocation_min_days   | int    | 否   | 冷热数据生效时间，默认 0                                   |
| storage_replies       | int    | 否   | 副本数                                                     |
| es_shards             | int    | 否   | ES 分片数                                                  |

### 参数列表（容器场景）

| 字段                     | 类型       | 必选 | 描述                                       |
| ------------------------ | ---------- | ---- | ------------------------------------------ |
| environment              | string     | 是   | 操作系统环境，必须为 `container`           |
| bk_biz_id                | int        | 是   | 业务 ID                                    |
| collector_config_name    | string     | 是   | 采集名称                                   |
| collector_config_name_en | string     | 是   | 采集项英文名                               |
| collector_scenario_id    | string     | 是   | 日志类型，枚举 `row`、`section`、`wineventlog`、`custom` |
| category_id              | string     | 是   | 分类 ID                                    |
| configs                  | list       | 是   | 容器日志配置，详见 Configs                 |
| bcs_cluster_id           | string     | 是   | BCS 集群 ID                                |
| add_pod_label            | bool       | 否   | 是否自动添加 Pod labels，默认 False        |
| add_pod_annotation       | bool       | 否   | 是否自动添加 Pod annotations，默认 False   |
| extra_labels             | List[dict] | 否   | 额外标签                                   |
| yaml_config_enabled      | bool       | 否   | 是否使用 YAML 配置模式，默认 False         |
| yaml_config              | string     | 否   | YAML 配置内容                              |
| storage_cluster_id       | int        | 否   | ES 集群 ID                                 |
| retention                | int        | 否   | 数据过期时间                               |
| etl_config               | string     | 否   | 清洗类型                                   |
| etl_params               | dict       | 否   | 清洗参数                                   |
| fields                   | list       | 否   | 字段配置                                   |
| alias_settings           | list       | 否   | 别名配置，详见 Alias Settings              |

#### TargetNodes

| 字段        | 类型   | 必选 | 描述         |
| ----------- | ------ | ---- | ------------ |
| id          | int    | 否   | 服务实例 ID  |
| bk_inst_id  | int    | 否   | 节点实例 ID  |
| bk_obj_id   | string | 否   | 节点实例对象 |
| ip          | string | 否   | IP           |
| bk_cloud_id | int    | 否   | 蓝鲸云区域 ID |

#### Plugin Params

| 字段          | 类型      | 必选 | 描述                              |
| ------------- | --------- | ---- | --------------------------------- |
| paths         | list      | 否   | 日志路径配置                      |
| conditions    | dict      | 否   | 过滤方式，详见 Plugin Condition   |
| exclude_files | List[str] | 否   | 日志路径排除，默认 `[]`           |
| tail_files    | bool      | 否   | 是否增量采集，默认 True           |

#### Alias Settings

| 字段        | 类型   | 必选 | 描述     |
| ----------- | ------ | ---- | -------- |
| field_name  | string | 是   | 原字段名 |
| query_alias | string | 是   | 别名     |
| path_type   | string | 是   | 字段类型 |

## 请求参数示例（物理环境）

```json
{
  "es_shards": 1,
  "storage_replies": 1,
  "description": "11111"
}
```

## 请求参数示例（容器环境）

```json
{
  "collector_config_name": "test_fast_create1",
  "collector_config_name_en": "test_fast_create1",
  "collector_scenario_id": "row",
  "description": "test_fast_create1",
  "environment": "container",
  "data_link_id": 1,
  "category_id": "host_process",
  "bcs_cluster_id": "BCS-K8S-00000",
  "add_pod_label": false,
  "add_pod_annotation": false,
  "extra_labels": [],
  "configs": [
    {
      "data_encoding": "UTF-8",
      "container": {"workload_type": "", "workload_name": "", "container_name": ""},
      "params": {
        "paths": ["/home/log"],
        "conditions": {"type": "none"}
      },
      "collector_type": "container_log_config",
      "namespaces": ["apm-demo"],
      "label_selector": {"match_labels": [], "match_expressions": []},
      "annotation_selector": {"match_annotations": []}
    }
  ],
  "yaml_config": "",
  "yaml_config_enabled": false,
  "bk_biz_id": "2",
  "storage_cluster_id": 6,
  "retention": 1,
  "es_shards": 1,
  "etl_config": "bk_log_json",
  "alias_settings": []
}
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "collector_config_id": 1
  }
}
```
