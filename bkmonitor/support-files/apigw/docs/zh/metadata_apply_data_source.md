### 功能描述

基于监控 DataSource 元信息生成独立的 BKBase DataSource 配置，并下发到指定 namespace。通过 `metadata.labels.raw_data_id` 标识已有数据源，不依赖已有 DataIdConfig 登记，不携带 DataId 引用。仅供内部应用调用，需要应用认证和资源权限。

下发成功后按租户、目标 namespace 和资源名创建或更新 DataIdConfig，记录 bk_data_id 和业务 ID；下发失败不写登记。此接口不会创建远端 DataId 或复制采集链路，不修改监控 DataSource，不持续同步后续配置。DataIdConfig 定时同步仅处理 bkmonitor、bklog，其他 namespace 的登记不参与该同步。资源名称固定为 `bkm_datasource_{bk_data_id}`，重复调用更新目标 namespace 中的同名资源。

### 请求方法与路径

`POST /app/metadata/apply_data_source/`

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_tenant_id | string | 否 | 沿用请求租户上下文；有请求租户时优先使用请求租户 |
| bk_data_id | int | 是 | 当前租户已有的数据源 ID |
| target_namespace | string | 是 | DataSource 的目标 namespace，最长 64 字符；禁止使用受管命名空间 bkmonitor、bklog |

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
    "name": "bkm_datasource_1605502",
    "target_namespace": "shared"
  }
}
```

`name` 为生成的目标 DataSource 名称。成功仅表示 BKBase 接受下发请求，不代表资源已就绪。数据源不存在或 BKBase 下发失败时返回错误。
