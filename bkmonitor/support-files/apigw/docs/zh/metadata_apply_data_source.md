### 功能描述

将当前租户在 `bkmonitor` 或 `bklog` 已登记的 DataId 以原名下发到目标项目。目标配置的 `metadata.namespace` 为目标项目，`spec.bizId` 为该项目所属业务。副本复用原 Data ID、Kafka channel 和 topic。仅供内部应用调用，需要应用认证和资源权限。

BKBase 接受下发后，metadata 更新目标项目的本地 DataIdConfig 登记。重复调用更新同名资源。对旧接口已共享的项目，再次调用会替换本地的 `bkm_datasource_{bk_data_id}` 登记。

### 请求方法与路径

`POST /app/metadata/apply_data_source/`

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| bk_tenant_id | string | 否 | 沿用请求租户上下文；有请求租户时优先使用请求租户 |
| bk_data_id | int | 是 | 当前租户已有的数据源 ID |
| target_namespace | string | 是 | DataId 的目标 namespace，最长 64 字符，受管命名空间 bkmonitor、bklog 除外 |
| bk_biz_id | int | 否 | 目标项目所属业务 ID。省略时查询 BKBase 项目的业务归属 |

### 请求示例

```json
{
  "bk_data_id": 1605502,
  "target_namespace": "shared",
  "bk_biz_id": 591
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
    "name": "bkm_did_1605502_example",
    "target_namespace": "shared"
  }
}
```

`name` 为源 DataId 在目标项目中沿用的资源名称。成功表示 BKBase 已接受下发请求，资源就绪状态由 BKBase 异步更新。
