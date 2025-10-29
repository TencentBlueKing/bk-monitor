### 功能描述

获取用户空间列表，支持根据用户权限过滤空间，可选择显示所有空间或仅显示用户有权限的空间。

### 请求参数

| 字段        | 类型    | 必须 | 默认值 | 描述                                    |
|-----------|-------|----|-----|---------------------------------------|
| bk_tenant_id | string| 是  | -   | 租户ID                                 |
| show_all  | bool  | 否  | false | 是否显示所有空间（true：显示所有，false：仅显示有权限的） |
| show_detail | bool | 否  | false | 是否显示详细信息（包含功能信息）                    |

### 请求参数示例

```
# 获取用户有权限的空间列表
GET /api/v3/meta/list_spaces/by_user/?bk_tenant_id=default

# 获取所有空间列表
GET /api/v3/meta/list_spaces/by_user/?bk_tenant_id=default&show_all=true

# 获取详细空间信息（包含功能信息）
GET /api/v3/meta/list_spaces/by_user/?bk_tenant_id=default&show_detail=true

# 获取所有空间的详细信息
GET /api/v3/meta/list_spaces/by_user/?bk_tenant_id=default&show_all=true&show_detail=true
```

### 响应参数

| 字段       | 类型   | 描述         |
|----------|------|------------|
| result   | bool | 请求是否成功     |
| code     | int  | 返回的状态码     |
| message  | string | 描述信息       |
| data     | list | 空间列表数据     |
| request_id | string | 请求ID       |

#### data.item 字段说明

| 字段            | 类型     | 描述                                      |
|---------------|--------|----------------------------------------|
| id            | int    | 空间ID                                   |
| space_uid     | string | 空间唯一标识                                 |
| space_id      | string | 空间标识                                   |
| space_name    | string | 空间名称                                   |
| space_code    | string | 空间编码                                   |
| space_type_id | string | 空间类型ID（bkcc：配置平台，bkci：蓝盾，bksaas：PaaS等） |
| bk_biz_id     | int    | 业务ID                                   |
| bk_tenant_id  | string | 租户ID                                   |
| display_name  | string | 显示名称                                   |
| func_info     | object | 功能信息（仅当show_detail=true时返回）            |

#### func_info 字段说明（仅当show_detail=true时返回）

| 字段               | 类型  | 描述                    |
|------------------|-----|----------------------|
| apm              | int | APM功能是否可用（1：可用，0：不可用） |
| custom_report    | int | 自定义上报功能是否可用           |
| host_collect     | int | 主机采集功能是否可用            |
| container_collect| int | 容器采集功能是否可用            |
| host_process     | int | 主机进程功能是否可用            |
| uptime_check     | int | 拨测功能是否可用              |
| k8s              | int | Kubernetes功能是否可用      |
| ci_builder       | int | CI构建功能是否可用            |
| paas_app         | int | PaaS应用功能是否可用          |

### 响应参数示例

#### 基本响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "space_uid": "bkcc__2",
      "space_id": "2",
      "space_name": "蓝鲸",
      "space_code": "",
      "space_type_id": "bkcc",
      "bk_biz_id": 2,
      "bk_tenant_id": "default",
      "display_name": "蓝鲸"
    },
    {
      "id": 2,
      "space_uid": "bkci__demo",
      "space_id": "demo",
      "space_name": "演示项目",
      "space_code": "demo",
      "space_type_id": "bkci",
      "bk_biz_id": -1,
      "bk_tenant_id": "default",
      "display_name": "演示项目"
    }
  ],
  "request_id": "xxx-xxx-xxx-xxx"
}
```

#### 详细响应示例（show_detail=true）

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "space_uid": "bkcc__2",
      "space_id": "2",
      "space_name": "蓝鲸",
      "space_code": "",
      "space_type_id": "bkcc",
      "bk_biz_id": 2,
      "bk_tenant_id": "default",
      "display_name": "蓝鲸",
      "func_info": {
        "apm": 1,
        "custom_report": 1,
        "host_collect": 1,
        "container_collect": 0,
        "host_process": 1,
        "uptime_check": 1,
        "k8s": 1,
        "ci_builder": 0,
        "paas_app": 0
      }
    },
    {
      "id": 2,
      "space_uid": "bkci__demo",
      "space_id": "demo",
      "space_name": "演示项目",
      "space_code": "demo",
      "space_type_id": "bkci",
      "bk_biz_id": -1,
      "bk_tenant_id": "default",
      "display_name": "演示项目",
      "func_info": {
        "apm": 1,
        "custom_report": 1,
        "host_collect": 0,
        "container_collect": 1,
        "host_process": 0,
        "uptime_check": 0,
        "k8s": 1,
        "ci_builder": 1,
        "paas_app": 0
      }
    }
  ],
  "request_id": "xxx-xxx-xxx-xxx"
}
```

### 特殊说明

1. **权限控制**：
   - 当 `show_all=false` 时，只返回用户有 `VIEW_BUSINESS` 权限的空间
   - 当 `show_all=true` 时，返回所有空间（需要相应权限）
   - 对于外部用户，会根据 `ExternalPermission` 表进行权限过滤

2. **空间类型**：
   - `bkcc`：配置平台业务空间
   - `bkci`：蓝盾项目空间
   - `bksaas`：PaaS应用空间
   - `default`：默认空间类型

3. **功能可用性**：
   - 功能可用性基于空间类型和配置进行判断
   - 不同空间类型支持的功能不同
   - 功能信息仅在 `show_detail=true` 时返回

4. **租户过滤**：
   - 返回结果会根据 `bk_tenant_id` 进行过滤
   - 只返回匹配指定租户的空间