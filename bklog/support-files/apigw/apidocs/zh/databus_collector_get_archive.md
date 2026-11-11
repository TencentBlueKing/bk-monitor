## 功能描述

按采集项查询其日志归档配置。没有归档时返回 `null`，调用方可据此决定是否需要创建。

## 请求参数

### 鉴权头

| 参数名称      | 参数类型 | 必须 | 参数说明     |
| ------------- | -------- | ---- | ------------ |
| bk_app_code   | string   | 是   | 蓝鲸应用ID   |
| bk_app_secret | string   | 是   | 蓝鲸应用秘钥 |
| bk_username   | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段                | 类型 | 必选 | 描述      |
| ------------------- | ---- | ---- | --------- |
| collector_config_id | int  | 是   | 采集项 ID |

## 返回结果示例

有归档：

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

没有归档：

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": null
}
```

## 注意事项

- 需要具备该采集项的「管理采集项」权限。
- `snapshot_days` 为 `0` 表示永久归档。
