### 功能描述

创建/保存采集配置

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段                     | 类型   | 是否必选 | 描述                          |
| ---------------------- | ---- | ---- | --------------------------- |
| bk_biz_id              | int  | 是    | 业务 ID                       |
| id                     | int  | 否    | 采集配置 id                     |
| name                   | str  | 是    | 采集配置名称                      |
| collect_type           | str  | 是    | 采集方式                        |
| target_object_type     | str  | 是    | 采集对象类型                      |
| target_node_type       | str  | 是    | 采集目标类型                      |
| plugin_id              | str  | 是    | 插件 ID                       |
| target_nodes           | List | 是    | 节点列表，可空                     |
| remote_collecting_host | Dict | 否    | 远程采集配置                      |
| params                 | Dict | 是    | 采集配置参数                      |
| label                  | str  | 是    | 二级标签                        |
| operation              | str  | 是    | 操作类型, \["EDIT", "ADD_DEL"\] |
| metric_relabel_configs | List | 否    | 指标重新配置标志                    |

#### 请求示例

```json
{
    "name": "test_hack",
    "bk_biz_id": 2,
    "collect_type": "Process",
    "target_object_type": "HOST",
    "plugin_id": "bkprocessbeat",
    "params": {
        "collector": {
            "period": 60,
            "timeout": 60
        },
        "plugin": {},
        "process": {
            "match_type": "command",
            "pid_path": "",
            "process_name": "",
            "match_pattern": "ssh",
            "exclude_pattern": "",
            "extract_pattern": "",
            "port_detect": true,
            "labels": {}
        }
    },
    "label": "host_process",
    "target_node_type": "INSTANCE",
    "target_nodes": [
        {
            "bk_host_id": 185,
            "ip": "127.0.0.1",
            "bk_cloud_id": 0
        }
    ],
    "id": 280
}
```

### 返回结果

| 字段      | 类型     | 描述     |
| ------- | ------ | ------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 数据     |

#### data 字段说明

| 字段            | 类型   | 描述       |
| ------------- | ---- | -------- |
| id            | int  | 采集配置 ID   |
| deployment_id | int  | 部署版本 ID   |
| can_rollback  | bool | 是否能够回滚   |
| diff_node     | Dict | 不同节点差异部分 |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "diff_node": {
      "is_modified": true,
      "added": [
        {
          "bk_host_id": 185
        }
      ],
      "updated": [],
      "removed": [],
      "unchanged": []
    },
    "can_rollback": true,
    "id": 280,
    "deployment_id": 518
  }
}
```
