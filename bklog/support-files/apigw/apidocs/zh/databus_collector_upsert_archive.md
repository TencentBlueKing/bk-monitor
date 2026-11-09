## 功能描述

按采集项幂等地创建或更新日志归档配置，可安全重试。调用方无需维护 `archive_config_id`。

后端路径：`PUT /api/v1/databus/collectors/{collector_config_id}/archive/`，`Content-Type: application/json`。

行为说明：

- 采集项没有归档：创建归档配置，并在 Metadata 创建结果表快照配置。
- 已有归档且快照仓库相同：更新归档天数；参数与现状一致时直接返回现状，不调用 Metadata。
- 已有归档但快照仓库不同：返回错误，不做隐式换仓库，需先调用 `DELETE` 再重建。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段                | 类型 | 必选 | 描述      |
| ------------------- | ---- | ---- | --------- |
| collector_config_id | int  | 是   | 采集项 ID |

### 参数列表

| 字段                            | 类型   | 必选 | 描述                                        |
| ------------------------------- | ------ | ---- | ------------------------------------------- |
| target_snapshot_repository_name | string | 是   | 目标快照仓库名称，最长 255 字符             |
| snapshot_days                   | int    | 是   | 归档存储天数，`0` 表示永久，不允许负数      |

`bk_biz_id` 取自采集项，接口不接受调用方传入。

## 请求示例

```json
{
  "target_snapshot_repository_name": "2_bklog_demo",
  "snapshot_days": 30
}
```

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": {
    "archive_config_id": 12,
    "collector_config_id": 34,
    "bk_biz_id": 2,
    "target_snapshot_repository_name": "2_bklog_demo",
    "snapshot_days": 30
  }
}
```

## 推荐调用流程

1. `POST /databus_collectors/fast_create/`：创建采集项，显式传入 `storage_cluster_id`。
2. `GET /databus/storage/{cluster_id}/repository/`：查询该集群下可用的快照仓库。
3. `PUT /databus/collectors/{collector_config_id}/archive/`：设置归档；失败可直接重试。

## 注意事项

- 需要具备该采集项的「管理采集项」权限。
- 仅支持存储类型为 ES 的采集项；Doris 等其他存储类型会返回明确错误。
- `target_snapshot_repository_name` 必须是采集项所在存储集群上已存在、且在快照仓库列表中可见的仓库，否则返回错误。
- 采集项刚创建、结果表尚未就绪时会返回错误，可稍后重试。
- 更换快照仓库会丢弃已归档的快照，因此必须显式先删除归档。
- 错误码：`3631805` 存储类型不支持归档；`3631806` 快照仓库不属于采集项存储集群；`3631807` 更换仓库需先删除；`3631808` 结果表尚未就绪。
