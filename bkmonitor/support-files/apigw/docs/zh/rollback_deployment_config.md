### 功能描述

采集配置回滚

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段 | 类型  | 必选 | 描述     |
|----|-----|----|--------|
| id | int | 是  | 采集配置ID |

#### 请求示例

```json
{
  "id": 1027
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | str  | 响应结果   |

#### data

| 字段            | 类型   | 描述       |
|---------------|------|----------|
| id            | int  | 采集配置ID   |
| deployment_id | int  | 采集部署配置ID |
| diff_node     | dict | 回滚部署信息   |

#### data.diff_node

| 字段          | 类型         | 描述      |
|-------------|------------|---------|
| is_modified | bool       | 是否为修改操作 |
| added       | list[dict] | 增加的节点   |
| updated     | list[dict] | 更新的节点   |
| removed     | list[dict] | 移除的节点   |
| unchanged   | list[dict] | 未变更的节点  |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "diff_node": {
      "is_modified": true,
      "added": [],
      "updated": [],
      "removed": [
        {
          "bk_host_id": 96888
        }
      ],
      "unchanged": [
        {
          "bk_host_id": 170118
        }
      ]
    },
    "id": 1027,
    "deployment_id": 2900
  }
}
```

