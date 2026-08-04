## 功能描述

快速创建一个采集项，覆盖普通主机日志、Windows 日志与普通容器日志，并完成清洗与存储配置。

后端路径：`POST /api/v1/databus/collectors/fast_create/`，`Content-Type: application/json`。

> 说明：本接口仅覆盖通用采集项，BCS 专用采集项管理接口不在开放范围内。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 参数列表（物理环境）

| 字段                     | 类型   | 必选 | 描述                                                                 |
| ------------------------ | ------ | ---- | -------------------------------------------------------------------- |
| bk_biz_id                | int    | 是   | 业务 ID                                                              |
| collector_config_name    | string | 是   | 采集项名称                                                           |
| collector_config_name_en | string | 是   | 采集项英文名                                                         |
| collector_scenario_id    | string | 是   | 日志类型，枚举 `row`、`section`、`wineventlog`、`custom`             |
| data_link_id             | string | 否   | 数据链路 ID                                                          |
| category_id              | string | 是   | 分类 ID，枚举 `os`、`application`、`host`、`other_rt`                |
| target_object_type       | string | 是   | 目标类型，枚举 `SERVICE`、`HOST`                                     |
| target_node_type         | string | 是   | 节点类型，枚举 `TOPO`、`INSTANCE`、`SERVICE_TEMPLATE`、`SET_TEMPLATE`、`DYNAMIC_GROUP` |
| target_nodes             | list   | 否   | 目标节点，详见 TargetNodes                                          |
| data_encoding            | string | 否   | 编码，默认 UTF-8                                                     |
| description              | string | 否   | 描述信息                                                             |
| environment              | string | 否   | 操作系统环境，枚举 `linux`、`windows`                               |
| params                   | dict   | 是   | 采集插件参数，详见 Plugin Params                                    |
| etl_config               | string | 否   | 清洗类型，枚举 `bk_log_text`、`bk_log_json`、`bk_log_delimiter`、`bk_log_regexp`、`custom`，默认 `bk_log_text` |
| etl_params               | dict   | 否   | 清洗参数，详见 ETL Params                                           |
| fields                   | list   | 否   | 字段配置，详见 ETL Fields                                          |
| storage_cluster_id       | int    | 是   | ES 集群 ID                                                          |
| retention                | int    | 否   | 数据过期时间                                                        |
| allocation_min_days      | int    | 否   | 冷热数据生效时间，默认 0                                            |
| storage_replies          | int    | 否   | 副本数                                                              |
| es_shards                | int    | 否   | ES 分片数                                                           |

### 参数列表（容器场景）

| 字段                     | 类型       | 必选 | 描述                                       |
| ------------------------ | ---------- | ---- | ------------------------------------------ |
| environment              | string     | 是   | 操作系统环境，必须为 `container`           |
| bk_biz_id                | int        | 是   | 业务 ID                                    |
| collector_config_name    | string     | 是   | 采集名称                                   |
| collector_config_name_en | string     | 是   | 采集项英文名                               |
| collector_scenario_id    | string     | 是   | 日志类型，枚举 `row`、`section`、`wineventlog`、`custom` |
| category_id              | string     | 是   | 分类 ID，枚举 `os`、`application`、`host`、`other_rt` |
| bcs_cluster_id           | string     | 是   | BCS 集群 ID                                |
| configs                  | list       | 是   | 容器日志配置，详见 Configs                 |
| add_pod_label            | bool       | 否   | 是否自动添加 Pod labels，默认 False        |
| add_pod_annotation       | bool       | 否   | 是否自动添加 Pod annotations，默认 False   |
| extra_labels             | List[dict] | 否   | 额外标签，详见 Label                       |
| yaml_config_enabled      | bool       | 否   | 是否使用 YAML 配置模式，默认 False         |
| yaml_config              | string     | 否   | YAML 配置内容，默认空字符串                |
| etl_config               | string     | 否   | 清洗类型，默认 `bk_log_text`               |
| storage_cluster_id       | int        | 否   | ES 集群 ID                                 |
| retention                | int        | 否   | 数据过期时间                               |
| etl_params               | dict       | 否   | 清洗参数，详见 ETL Params                  |
| fields                   | list       | 否   | 字段配置，详见 ETL Fields                  |

#### TargetNodes

| 字段        | 类型   | 必选 | 描述         |
| ----------- | ------ | ---- | ------------ |
| id          | int    | 否   | 服务实例 ID  |
| bk_inst_id  | int    | 否   | 节点实例 ID  |
| bk_obj_id   | string | 否   | 节点实例对象 |
| ip          | string | 否   | IP           |
| bk_cloud_id | int    | 否   | 蓝鲸云区域 ID |

#### Plugin Params

| 字段              | 类型      | 必选 | 描述                              |
| ----------------- | --------- | ---- | --------------------------------- |
| paths             | list      | 否   | 日志路径配置                      |
| conditions        | dict      | 否   | 过滤方式，详见 Plugin Condition   |
| exclude_files     | List[str] | 否   | 日志路径排除，默认 `[]`           |
| multiline_pattern | string    | 否   | 行首正则表达式                    |
| multiline_max_lines | int     | 否   | 最多匹配行数，最大 5000           |
| multiline_timeout | int       | 否   | 匹配超时时间，最大 10             |
| tail_files        | bool      | 否   | 是否增量采集，默认 True           |
| winlog_name       | List[str] | 否   | Windows 事件名称                  |
| winlog_level      | List[str] | 否   | Windows 事件等级                  |
| winlog_event_id   | List[str] | 否   | Windows 事件 ID                   |

#### Plugin Condition

| 字段              | 类型   | 必选 | 描述                               |
| ----------------- | ------ | ---- | ---------------------------------- |
| type              | string | 是   | 过滤方式类型，枚举 `match`、`separator` |
| match_type        | string | 否   | 过滤方式，枚举 `include`、`exclude` |
| match_content     | string | 否   | 过滤内容                           |
| separator         | string | 否   | 分隔符                             |
| separator_filters | dict   | 否   | 过滤规则                           |

#### ETL Params

| 字段                 | 类型   | 必选 | 描述                        |
| -------------------- | ------ | ---- | --------------------------- |
| separator_regexp     | string | 否   | 正则表达式                  |
| separator            | string | 否   | 分隔符                      |
| retain_original_text | bool   | 否   | 是否保留原文，默认 True     |
| retain_extra_json    | bool   | 否   | 是否保留未定义 JSON 字段，默认 False |
| enable_retain_content | bool  | 否   | 是否保留失败日志，默认 True |

#### ETL Fields

| 字段         | 类型   | 必选 | 描述         |
| ------------ | ------ | ---- | ------------ |
| field_index  | int    | 否   | 字段顺序     |
| field_name   | string | 否   | 字段名称     |
| alias_name   | string | 否   | 别名         |
| field_type   | string | 否   | 类型         |
| is_analyzed  | bool   | 否   | 是否分词     |
| is_dimension | bool   | 否   | 是否维度     |
| is_time      | bool   | 否   | 是否时间字段 |
| is_delete    | bool   | 是   | 是否删除     |

#### Configs（容器场景）

| 字段                | 类型      | 必选 | 描述                                                     |
| ------------------- | --------- | ---- | -------------------------------------------------------- |
| namespaces          | List[str] | 否   | 命名空间，默认空列表                                    |
| namespaces_exclude  | List[str] | 否   | 排除命名空间，默认空列表                                |
| container           | dict      | 否   | 指定容器                                                |
| label_selector      | dict      | 否   | 标签选择器                                              |
| annotation_selector | dict      | 否   | 注解选择器                                              |
| paths               | List[str] | 否   | 日志路径                                                |
| data_encoding       | str       | 否   | 日志字符集，默认 UTF-8                                  |
| params              | dict      | 是   | 插件参数，详见 Plugin Params                            |
| collector_type      | str       | 是   | 容器采集类型，枚举 `container_log_config`、`node_log_config`、`std_log_config` |

## 请求参数示例（物理环境）

```json
{
  "bk_biz_id": 1,
  "collector_config_name": "20220729_88",
  "collector_config_name_en": "20220729_en_88",
  "collector_scenario_id": "row",
  "category_id": "os",
  "target_object_type": "HOST",
  "target_node_type": "TOPO",
  "target_nodes": [{"bk_inst_id": 2, "bk_obj_id": "biz"}],
  "params": {
    "paths": ["/var/log"],
    "conditions": {"type": "match"}
  },
  "storage_cluster_id": 1,
  "es_shards": 1,
  "retention": 1
}
```

## 请求参数示例（容器环境）

```json
{
  "collector_config_name": "test_fast_create5",
  "collector_config_name_en": "test_fast_create5",
  "collector_scenario_id": "row",
  "description": "test_fast_create5",
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
      "namespaces": ["blueking"],
      "label_selector": {"match_labels": [], "match_expressions": []},
      "annotation_selector": {"match_annotations": []}
    }
  ],
  "yaml_config": "",
  "yaml_config_enabled": false,
  "bk_biz_id": "2",
  "etl_config": "bk_log_json",
  "storage_cluster_id": 6,
  "retention": 3,
  "es_shards": 1
}
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "collector_config_id": 1,
    "bk_data_id": 1,
    "subscription_id": 1,
    "task_id_list": ["1"],
    "index_set_id": 1
  }
}
```

### 返回结果说明

| 字段                | 类型 | 描述           |
| ------------------- | ---- | -------------- |
| collector_config_id | int  | 采集项 ID      |
| bk_data_id          | int  | 数据 ID        |
| subscription_id     | int  | 节点管理订阅 ID |
| task_id_list        | list | 任务 ID 列表   |
| index_set_id        | int  | 索引集 ID      |
