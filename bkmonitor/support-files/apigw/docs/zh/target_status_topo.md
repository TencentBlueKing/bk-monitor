### 功能描述

获取采集对象和状态拓扑

### 请求参数

| 字段名           | 类型    | 是否必选 | 描述 |
|------------------|---------|----------|------|
| `bk_biz_id`      | `int`   | 是       | 业务ID |
| `id`             | `int`   | 是       | 采集配置ID |
| `only_instance`  | `bool`  | 否       | 是否仅显示实例节点（默认为 `False`） |

### 请求参数示例
```json
{
  "bk_biz_id": 2,
  "id": 105,
  "only_instance": false
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | list | 数据     |

#### data
`情况一：目标类型为 INSTANCE（静态实例）`

| 字段         | 类型  | 描述     |
|------------|-----|--------|
| id         | str | 节点唯一标识 |
| name       | str | 节点显示名称 |
| alias_name | str | 主机别名   |
| bk_host_id | int | 主机ID   |
| status     | str | 采集状态   |
| ip         | str | 主机IP   |
| bk_cloud_id  | int   | 云区域ID  |

`情况二：目标类型为拓扑类（TOPO / SERVICE_TEMPLATE / SET_TEMPLATE）`

| 字段名         | 类型                | 描述                     |
|----------------|---------------------|--------------------------|
| id             | `str`               | 节点唯一标识，格式如 `"set|5"` |
| name           | `str`               | 集群名称                 |
| bk_obj_id      | `str`               | 业务对象 ID，此处为 `"set"` |
| bk_obj_name    | `str`               | 业务对象名称，此处为 `"集群"` |
| bk_inst_id     | `int`               | 实例 ID                  |
| bk_inst_name   | `str`               | 实例名称                 |
| children       | `List[ModuleNode]`  | 子模块列表               |

ModuleNode（模块节点）

| 字段名         | 类型                | 描述                     |
|----------------|---------------------|--------------------------|
| id             | `str`               | 节点唯一标识，格式如 `"module|12558"` |
| name           | `str`               | 模块名称                 |
| bk_obj_id      | `str`               | 业务对象 ID，此处为 `"module"` |
| bk_obj_name    | `str`               | 业务对象名称，此处为 `"模块"` |
| bk_inst_id     | `int`               | 模块实例 ID              |
| bk_inst_name   | `str`               | 模块实例名称             |
| children       | `List[HostNode]`    | 该模块下的主机列表       |

HostNode（主机节点）

| 字段名         | 类型      | 描述                     |
|----------------|-----------|--------------------------|
| id             | `int`     | 主机在系统中的唯一 ID    |
| name           | `str`     | 主机名（通常为 IP）      |
| ip             | `str`     | 主机 IP 地址             |
| bk_cloud_id    | `int`     | 云区域 ID                |
| status         | `str`     | 主机状态 |
| bk_host_id     | `int`     | 主机 ID |
| alias_name     | `str`     | 主机别名                 |

`情况三：目标类型为 DYNAMIC_GROUP（动态分组）`

| 字段名        | 类型       | 描述                                      |
|---------------|----------|-------------------------------------------|
| node_path     | str      | 节点路径               |
| label_name    | str      | 标签名                  |
| is_label      | bool     | 是否为标签节点                            |
| children      | List[HostInfo] | 该分组下包含的主机列表                    |
| name          | str      | 分组名称          |
| id            | str      | 分组唯一标识 |

HostInfo（主机信息）

| 字段名           | 类型  | 描述                                               |
|------------------|-----|----------------------------------------------------|
| instance_id      | str | 实例唯一标识   |
| ip               | str | 主机 IP 地址                                       |
| bk_cloud_id      | int | 云区域 ID                                          |
| bk_host_id       | int | 主机在 CMDB 中的 ID                                |
| bk_host_name     | str | 主机名                          |
| bk_supplier_id   | str | 供应商 ID                 |
| task_id          | int | 关联的任务 ID                                      |
| status           | str | 主机状态                          |
| plugin_version   | str | 插件版本号                                         |
| log              | str | 操作日志                              |
| action           | str | 当前操作类型                 |
| steps            | Dict[str, str]| 各组件操作步骤状态 |
| instance_name    | str | 实例显示名称                          |
| bk_module_ids    | List[int] | 所属模块 ID 列表                                   |
| id               | int | 主机 ID                   |
| name             | str | 主机显示名称                        |
| alias_name       | str | 主机别名                           |

### 响应参数示例
`情况一：目标类型为 INSTANCE（静态实例）`
```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": "5",
      "name": null,
      "ip": "127.0.0.1",
      "bk_cloud_id": 0,
      "status": "NODATA",
      "bk_host_id": 5,
      "alias_name": ""
    },
    {
      "id": "6",
      "name": null,
      "ip": "127.0.0.2",
      "bk_cloud_id": 0,
      "status": "NODATA",
      "bk_host_id": 6,
      "alias_name": ""
    }
  ]
}
```

`情况二：目标类型为拓扑类（TOPO / SERVICE_TEMPLATE / SET_TEMPLATE）`
```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": "set|5",
      "name": "公共组件",
      "bk_obj_id": "set",
      "bk_obj_name": "集群",
      "bk_inst_id": 5,
      "bk_inst_name": "公共组件",
      "children": [
        {
          "id": "module|12558",
          "name": "control",
          "bk_obj_id": "module",
          "bk_obj_name": "模块",
          "bk_inst_id": 12588,
          "bk_inst_name": "control",
          "children": [
            {
              "id": 3,
              "name": "127.0.0.1",
              "ip": "127.0.0.1",
              "bk_cloud_id": 0,
              "status": "SUCCESS",
              "bk_host_id": 3,
              "alias_name": "xxx-ee-control"
            }
          ]
        }
      ]
    }
  ]
}
```

`情况三：目标类型为 DYNAMIC_GROUP（动态分组）`
```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "node_path": "动态分组",
      "label_name": "",
      "is_label": false,
      "children": [
        {
          "instance_id": "host|instance|host|96588",
          "ip": "127.0.0.1",
          "bk_cloud_id": 0,
          "bk_host_id": 96568,
          "bk_host_name": "xx-38-149-xx",
          "bk_supplier_id": "0",
          "task_id": 45568888,
          "status": "NODATA",
          "plugin_version": "1.1",
          "log": "",
          "action": "install",
          "steps": {
            "bkmonitorbeat": "INSTALL"
          },
          "instance_name": "127.0.0.1",
          "bk_module_ids": [
            10557
          ],
          "id": 96568,
          "name": "127.0.0.1",
          "alias_name": "xx-38-149-xx"
        }
      ],
      "name": "动态分组1",
      "id": "xxo02qijv6d06mf38j88"
    }
  ]
}
```
