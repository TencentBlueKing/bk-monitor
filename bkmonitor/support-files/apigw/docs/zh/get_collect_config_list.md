
### 功能描述

获取采集配置列表


#### 接口参数

该接口无请求参数

### 返回结果

| 字段      | 类型           | 描述         |
| ------- | ------------ | ---------- |
| result  | bool         | 请求是否成功     |
| code    | int          | 返回的状态码     |
| message | str          | 描述信息       |
| data    | List\[Dict\] | 采集配置基本信息列表 |

#### data 字段说明

| 字段                   | 类型   | 描述          |
| -------------------- | ---- | ----------- |
| id                   | int  | 采集配置基本信息 ID |
| bk_biz_id            | int  | 业务 ID       |
| name                 | str  | 配置名称        |
| collect_type         | str  | 采集方式        |
| plugin_id            | str  | 关联插件 id     |
| target_object_type   | str  | 采集对象类型      |
| deployment_config_id | int  | 当前的部署配置 ID  |
| cache_data           | str  | 缓存数据        |
| last_operation       | str  | 最近一次操作类型      |
| operation_result     | str  | 最近一次任务结果    |
| label                | str  | 二级标签        |
| create_time          | str  | 创建时间        |
| create_user          | str  | 创建人         |
| update_time          | str  | 修改时间        |
| update_user          | str  | 修改人         |
| is_deleted           | bool | 是否删除        |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 280,
      "name": "test_hack",
      "bk_biz_id": 2,
      "collect_type": "Process",
      "target_object_type": "HOST",
      "plugin_id": "bkprocessbeat",
      "deployment_config_id": 1,
      "label": "host_process",
      "create_time": "2025-01-07 18:38:29+0800",
      "create_user": "admin",
      "update_time": "2025-01-07 18:38:29+0800",
      "update_user": "admin",
      "is_deleted": false,
      "cache_data": "",
      "last_operation": "",
      "operation_result": ""
    }
  ]
}

```
