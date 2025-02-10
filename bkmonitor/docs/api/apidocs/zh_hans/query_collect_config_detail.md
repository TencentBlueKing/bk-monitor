### 功能描述

查询采集配置详情

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段        | 类型  | 必选  | 描述     |
| --------- | --- | --- | ------ |
| bk_biz_id | int | 是   | 业务 ID  |
| id        | int | 是   | 采集配置 ID |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "id": 323
}
```

### 返回结果

| 字段      | 类型     | 描述     |
| ------- | ------ | ------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 数据     |

#### data

| 字段                     | 类型   | 描述        |
| ---------------------- | ---- | --------- |
| id                     | int  | 采集配置 ID   |
| deployment_id          | int  | 部署版本历史 ID |
| name                   | str  | 采集配置名称    |
| bk_biz_id              | int  | 业务 ID     |
| collect_type           | str  | 采集方式      |
| label                  | str  | 二级标签      |
| target_object_type     | str  | 采集对象类型    |
| target_node_type       | str  | 采集目标类型    |
| target_nodes           | List | 采集目标节点列表  |
| params                 | Dict | 采集参数配置    |
| remote_collecting_host | Dict | 远程采集机器    |
| plugin_info            | Dict | 插件信息详情    |
| target                 | List | 采集目标信息    |
| subscription_id        | int  | 节点管理订阅 ID |
| label_info             | str  | 标签信息      |
| create_time            | str  | 创建时间      |
| create_user            | str  | 创建人       |
| update_time            | str  | 修改时间      |
| update_user            | str  | 修改人       |

##### data.plugin_info

| 字段                   | 类型        | 描述                                 |
| -------------------- | --------- | ---------------------------------- |
| plugin_id            | int       | 采集插件源信息 ID                         |
| plugin_display_name  | str       | 插件别名                               |
| plugin_type          | str       | 插件类型                               |
| tag                  | str       | 插件标签                               |
| label                | str       | 二级标签                               |
| status               | str       | 当前状态, \["normal", "draft"\]        |
| logo                 | str       | logo 内容 bytes 类型                   |
| collector_json       | dict      | 采集器配置                              |
| config_json          | dict      | 参数配置                               |
| metric_json          | List      | 指标配置                               |
| description_md       | str       | 插件描述, markdown 文本                  |
| config_version       | int       | 插件版本                               |
| info_version         | int       | 插件信息版本                             |
| stage                | str       | 版本阶段                               |
| bk_biz_id            | int       | 业务 ID                              |
| signature            | str       | 版本签名                               |
| is_support_remote    | bool      | 是否支持远程采集                           |
| is_official          | bool      | 是否是官方的, 官方插件 ID 都是以 bkplugin_ 作为前缀 |
| is_safety            | bool      | 版本签名是否有效                           |
| create_user          | str       | 创建人                                |
| update_user          | str       | 修改人                                |
| os_type_list         | List[str] | 获取该版本支持的操作系统类型                     |
| create_time          | str       | 创建时间                               |
| update_time          | str       | 修改时间                               |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 323,
    "deployment_id": 519,
    "name": "test_hack_copy",
    "bk_biz_id": 2,
    "collect_type": "Process",
    "label": "host_process",
    "target_object_type": "HOST",
    "target_node_type": "INSTANCE",
    "target_nodes": [
      {
        "bk_host_id": 185
      }
    ],
    "params": {
      "collector": {
        "period": 60,
        "timeout": 60,
        "metric_relabel_configs": []
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
      },
      "target_node_type": "INSTANCE",
      "target_object_type": "HOST"
    },
    "remote_collecting_host": null,
    "plugin_info": {
      "plugin_id": "bkprocessbeat",
      "plugin_display_name": "进程采集",
      "plugin_type": "Process",
      "tag": "",
      "logo": "",
      "collector_json": {},
      "config_json": [],
      "metric_json": [
        {
          "table_name": "perf",
          "table_desc": "perf",
          "fields": [
            {
              "description": "进程启动时间",
              "type": "double",
              "monitor_type": "metric",
              "unit": "none",
              "name": "cpu_start_time",
              "is_diff_metric": false,
              "is_active": true,
              "source_name": "",
              "is_manual": true
            }
          ],
          "table_id": "process.perf"
        }
      ],
      "description_md": "测试手动调整",
      "config_version": 1,
      "info_version": 1,
      "stage": "release",
      "bk_biz_id": 0,
      "signature": "default: {}\n",
      "is_support_remote": false,
      "is_official": false,
      "is_safety": true,
      "create_user": "admin",
      "update_user": "admin",
      "os_type_list": []
    },
    "target": [
      {
        "bk_host_id": 185,
        "display_name": "127.0.0.1",
        "bk_cloud_id": 0,
        "bk_cloud_name": "Default Area",
        "agent_status": null,
        "bk_os_type": "linux",
        "bk_supplier_id": "0",
        "is_external_ip": false,
        "is_innerip": true,
        "is_outerip": false,
        "ip": "127.0.0.1"
      }
    ],
    "subscription_id": 5131,
    "label_info": "主机&云平台-进程",
    "create_time": "2025-02-06 14:20:21+0800",
    "create_user": "admin",
    "update_time": "2025-02-06 14:20:48+0800",
    "update_user": "admin"
  }
}
```
