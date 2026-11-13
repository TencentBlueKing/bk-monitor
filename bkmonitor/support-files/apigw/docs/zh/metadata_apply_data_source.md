### 功能描述

将已有数据源的 BKBase DataSource 资源下发到指定 namespace，仍引用源 namespace 的 DataId。仅供内部应用调用，需要应用认证和资源权限。

此接口不会创建 DataId 或复制采集链路，不修改本地数据源，不持续同步后续配置。重复调用更新同名目标资源，允许已有 DataId 与目标 namespace 相同。内部按当前租户和数据源 ID 选择最近更新的 DataId 登记（更新时间相同时按记录 ID 倒序），自动使用其名称和 namespace。BKBase 必须支持跨 namespace 的 DataId 引用。

### 请求方法与路径

`POST /app/metadata/apply_data_source/`

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_tenant_id | string | 否 | 沿用请求租户上下文；有请求租户时优先使用请求租户 |
| bk_data_id | int | 是 | 当前租户已有的数据源 ID |
| target_namespace | string | 是 | DataSource 的目标 namespace，最长 64 字符 |

### 请求示例

```json
{
  "bk_data_id": 1605502,
  "target_namespace": "shared"
}
```

### 响应示例

```json
{
  "result": true,
  "code": 0,
  "message": "OK",
  "data": {
    "bk_data_id": 1605502,
    "name": "bkm_existing_source",
    "target_namespace": "shared"
  }
}
```

`name` 为源 DataId 的已注册名称，同时作为目标 DataSource 名称。成功仅表示 BKBase 接受下发请求，不代表资源已就绪。数据源不存在、源 DataId 未登记或 BKBase 下发失败时返回错误。
