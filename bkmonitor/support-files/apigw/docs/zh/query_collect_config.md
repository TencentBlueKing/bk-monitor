### 功能描述

查询采集配置列表


#### 接口参数

| 字段                   | 类型   | 必选  | 描述        |
| -------------------- | ---- | --- | --------- |
| bk_biz_id            | int  | 是   | 业务 ID     |
| refresh_status       | bool | 否   | 是否刷新状态    |
| search               | Dict | 否   | 搜索字段      |
| order                | str  | 否   | 排序字段      |
| disable_service_type | bool | 否   | 不需要服务分类   |
| page                 | int  | 否   | 页数, 默认 1  |
| limit                | int  | 否   | 大小, 默认 10 |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "refresh_status": false,
  "order": "-create_time",
  "search": {},
  "page": 1,
  "limit": 10
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

| 字段          | 类型           | 描述     |
| ----------- | ------------ | ------ |
| type_list   | List\[Dict\] | 插件类型类别 |
| config_list | List\[Dict\] | 配置列表   |
| total       | int          | 采集配置总数 |

##### data.type_list

| 字段   | 类型  | 描述        |
| ---- | --- | --------- |
| id   | str | 采集插件类型 ID |
| name | str | 采集插件类型名称  |

默认插件类型

| id          | name       |
| ----------- | ---------- |
| EXPORTER    | Exporter   |
| SCRIPT      | Script     |
| JMX         | JMX        |
| DATADOG     | DataDog    |
| PUSHGATEWAY | BK-Pull    |
| BUILT_IN    | BK-Monitor |
| LOG         | Log        |
| PROCESS     | Process    |
| SNMP_TRAP   | SNMP_Trap  |
| SNMP        | SNMP       |
| K8S         | K8S        |

##### data.config_list

| 字段                   | 类型   | 描述       |
| -------------------- | ---- | -------- |
| id                   | int  | 配置 ID    |
| name                 | str  | 配置名称     |
| bk_biz_id            | int  | 业务 ID    |
| space_name           | str  | 空间名称     |
| collect_type         | str  | 采集类型     |
| status               | str  | 配置状态: STARTED / STOPPED / DEPLOYING / STARTING / STOPPING / PREPARING (STARTED: 已启用, STOPPED: 已停用, DEPLOYING: 执行中, STARTING: 启用中, STOPPING: 停用中, PREPARING: 准备中)     |
| task_status          | str  | 任务状态: PREPARING / DEPLOYING / STOPPING / STARTING / STOPPED / SUCCESS / WARNING / FAILED / AUTO_DEPLOYING (PREPARING: 准备中, DEPLOYING: 执行中, STOPPING: 停用中, STARTING: 启用中, STOPPED: 已停用, SUCCESS: 上次任务执行下发全部成功, WARNING: 任务执行下发部分失败, FAILED: 上次任务调用失败/任务执行下发全部失败, AUTO_DEPLOYING: 自动执行中)     |
| target_object_type   | str  | 采集对象类型: SERVICE / HOST / CLUSTER (SERVICE: 服务, HOST: 主机, CLUSTER: 集群)   |
| target_node_type     | str  | 采集目标类型: TOPO / INSTANCE / SERVICE_TEMPLATE / SET_TEMPLATE / CLUSTER (TOPO: 拓扑, INSTANCE: 实例, SERVICE_TEMPLATE: 服务模板, SET_TEMPLATE: 集群模板, CLUSTER: 集群)  |
| plugin_id            | str  | 插件 ID     |
| target_nodes_count   | int  | 采集目标节点数量 |
| need_upgrade         | bool | 是否需要升级   |
| config_version       | int  | 插件版本     |
| info_version         | int  | 插件信息版本   |
| error_instance_count | int  | 报错实例数量   |
| total_instance_count | int  | 所有实例数量   |
| running_tasks        | List | 进行中的任务   |
| label_info           | str  | 标签信息     |
| label                | str  | 二级标签     |
| update_time          | str  | 修改时间     |
| update_user          | str  | 修改人      |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "type_list": [
      {
        "id": "Exporter",
        "name": "Exporter"
      }
    ],
    "config_list": [
      {
        "id": 325,
        "name": "test_hack_copy_copy",
        "bk_biz_id": 2,
        "space_name": "蓝鲸(业务)",
        "collect_type": "Process",
        "status": "STARTED",
        "task_status": "WARNING",
        "target_object_type": "HOST",
        "target_node_type": "INSTANCE",
        "plugin_id": "bkprocessbeat",
        "target_nodes_count": 2,
        "need_upgrade": false,
        "config_version": 1,
        "info_version": 1,
        "error_instance_count": 1,
        "total_instance_count": 2,
        "running_tasks": [],
        "label_info": "主机&云平台-进程",
        "label": "host_process",
        "update_time": "2025-02-06 15:46:38+0800",
        "update_user": "admin"
      }
    ],
    "total": 125
  }
}
```
