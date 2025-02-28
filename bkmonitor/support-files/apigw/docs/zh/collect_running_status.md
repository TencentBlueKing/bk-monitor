### 功能描述

获取采集配置主机的运行状态

### 请求参数

{{ common_args_desc }}

####          

| 字段   | 类型   | 必选 | 描述      |
|------|------|----|---------|
| id   | int  | 是  | 采集配置ID  |
| diff | bool | 否  | 是否只返回差异 |

#### 示例数据

```json
{
  "id": 26
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   | 
| data    | dict   | 数据     |

#### data

| 字段          | 类型   | 描述   |
|-------------|------|------|
| config_info | dict | 配置信息 |
| contents    | list | 状态信息 |

#### data.config_info

| 字段                 | 类型  | 描述       |
|--------------------|-----|----------|
| id                 | int | 采集配置ID   |
| name               | str | 采集配置名称   |
| bk_biz_id          | int | 业务ID     | 
| target_object_type | str | 采集对象类型   |
| target_node_type   | str | 采集目标类型   |
| plugin_id          | str | 插件ID     |
| label              | str | 标签       | 
| config_version     | int | 插件版本     |
| info_version       | int | 插件信息版本   |
| last_operation     | str | 最近一次操作类型 |

#### data.contents

| 字段                 | 类型   | 描述     |
|--------------------|------|--------|
| child              | list | 主机列表   |
| node_path          | str  | 节点路径   |
| label_name         | str  | 操作类型   | 
| is_label           | bool | 是否显示差异 |
| dynamic_group_name | str  | 动态分组名称 |
| dynamic_group_id   | str  | 动态分组ID |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "config_info": {
      "id": 941,
      "name": "上云环境Job分发节点Agent任务量采集",
      "bk_biz_id": 7,
      "target_object_type": "HOST",
      "target_node_type": "INSTANCE",
      "plugin_id": "bkte_agent_task_num_1",
      "label": "os",
      "config_version": 1,
      "info_version": 1,
      "last_operation": "CREATE"
    },
    "contents": [
      {
        "child": [
          {
            "instance_id": "host|instance|host|170090",
            "ip": "127.0.0.1",
            "bk_cloud_id": 0,
            "bk_host_id": 170090,
            "bk_host_name": "VM-241-175-tencentos",
            "bk_supplier_id": "0",
            "task_id": 32797714,
            "status": "SUCCESS",
            "plugin_version": "1.1",
            "log": "[bkte_agent_task_num_1] 部署插件-初始化进程状态",
            "action": "install",
            "steps": {
              "bkte_agent_task_num_1": "INSTALL",
              "bkmonitorbeat": "INSTALL"
            },
            "instance_name": "127.0.0.1",
            "bk_module_ids": [],
            "alert_histogram": [
              [
                1740100800000,
                0
              ],
              [
                1740100860000,
                0
              ],
              [
                1740100920000,
                0
              ]
            ]
          },
          {
            "instance_id": "host|instance|host|170091",
            "ip": "127.0.0.1",
            "bk_cloud_id": 0,
            "bk_host_id": 170091,
            "bk_host_name": "VM-241-16-tencentos",
            "bk_supplier_id": "0",
            "task_id": 32797714,
            "status": "SUCCESS",
            "plugin_version": "1.1",
            "log": "[bkte_agent_task_num_1] 部署插件-初始化进程状态",
            "action": "install",
            "steps": {
              "bkte_agent_task_num_1": "INSTALL",
              "bkmonitorbeat": "INSTALL"
            },
            "instance_name": "127.0.0.1",
            "bk_module_ids": [],
            "alert_histogram": [
              [
                1740100800000,
                0
              ],
              [
                1740100860000,
                0
              ],
              [
                1740100920000,
                0
              ]
            ]
          }
        ],
        "node_path": "主机",
        "label_name": "",
        "is_label": false
      }
    ]
  }
}
```
