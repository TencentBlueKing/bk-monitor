### 功能描述

查询采集配置节点状态

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段   | 类型   | 必选  | 描述                |
| ---- | ---- | --- | ----------------- |
| id   | int  | 是   | 采集配置 ID           |
| diff | bool | 否   | 是否只返回差异， 默认 False |

#### 请求示例

```json
{
  "id": 280,
  "bk_biz_id": 2
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

| 字段          | 类型           | 描述   |
| ----------- | ------------ | ---- |
| config_info | Dict         | 配置信息 |
| contents    | List\[Dict\] | 实例状态 |

##### data.config_info

| 字段                 | 类型  | 描述     |
| ------------------ | --- | ------ |
| id                 | int | 配置信息 ID |
| name               | str | 配置名称   |
| bk_biz_id          | int | 业务 ID   |
| target_object_type | str | 采集对象类型: SERVICE / HOST / CLUSTER (SERVICE: 服务, HOST: 主机, CLUSTER: 集群) |
| target_node_type   | str | 采集目标类型: TOPO / INSTANCE / SERVICE_TEMPLATE / SET_TEMPLATE / CLUSTER (TOPO: 拓扑, INSTANCE: 实例, SERVICE_TEMPLATE: 服务模板, SET_TEMPLATE: 集群模板, CLUSTER: 集群) |
| plugin_id          | str | 插件 ID   |
| label              | str | 二级标签   |
| config_version     | int | 插件版本   |
| info_version       | int | 插件信息版本 |
| last_operation     | str | 最后一次操作 |

##### data.contents

| 字段         | 类型           | 描述     |
| ---------- | ------------ | ------ |
| child      | List\[Dict\] |        |
| node_path  | str          | 目标对象类型 |
| label_name | str          | 标签名称   |
| is_label   | bool         | 是否是标签  |

##### data.contents.child

| 字段             | 类型       | 描述                 |
| -------------- | -------- | ------------------ |
| instance_id    | str      | 实例 ID              |
| instance_name  | str      | 实例名称               |
| status         | str      | 实例状态               |
| plugin_version | str      | 插件版本               |
| log            | str      | 日志                 |
| action         | str      | 执行动作               |
| steps          | Dict     | 操作步骤，需要对哪些插件执行什么操作 |
| ip             | str      | 实例 IP 地址           |
| bk_cloud_id    | int      | 云区域 ID              |
| bk_host_id     | int      | 主机 ID               |
| bk_host_name   | str      | 主机名称               |
| bk_supplier_id | str      | 开发商 ID              |
| task_id        | int      | 任务 ID               |
| bk_module_ids  | List     | 模块 ID 列表             |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "config_info": {
      "id": 280,
      "name": "test_hack",
      "bk_biz_id": 2,
      "target_object_type": "HOST",
      "target_node_type": "INSTANCE",
      "plugin_id": "bkprocessbeat",
      "label": "host_process",
      "config_version": 1,
      "info_version": 1,
      "last_operation": "ADD_DEL"
    },
    "contents": [
      {
        "child": [
          {
            "instance_id": "host|instance|host|185",
            "ip": "127.0.0.1",
            "bk_cloud_id": 0,
            "bk_host_id": 185,
            "bk_host_name": "VM-4-8-centos",
            "bk_supplier_id": "0",
            "task_id": 2572682,
            "status": "SUCCESS",
            "plugin_version": "1.1",
            "log": "",
            "action": "install",
            "steps": {
              "bkmonitorbeat": "INSTALL"
            },
            "instance_name": "127.0.0.1",
            "bk_module_ids": []
          }
        ],
        "node_path": "主机",
        "label_name": "ADD",
        "is_label": true
      }
    ]
  }
}
```
