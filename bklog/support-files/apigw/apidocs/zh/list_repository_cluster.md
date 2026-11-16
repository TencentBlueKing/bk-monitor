## 功能描述

查询指定存储集群下的快照仓库列表，用于为采集项选择日志归档的目标仓库。

只返回当前业务可见、且符合日志平台快照仓库命名约定的仓库。

## 请求参数

### 鉴权头

| 参数名称      | 参数类型 | 必须 | 参数说明     |
| ------------- | -------- | ---- | ------------ |
| bk_app_code   | string   | 是   | 蓝鲸应用ID   |
| bk_app_secret | string   | 是   | 蓝鲸应用秘钥 |
| bk_username   | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段       | 类型 | 必选 | 描述        |
| ---------- | ---- | ---- | ----------- |
| cluster_id | int  | 是   | 存储集群 ID |

### 查询参数

| 字段      | 类型 | 必选 | 描述    |
| --------- | ---- | ---- | ------- |
| bk_biz_id | int  | 是   | 业务 ID |

## 返回结果示例

```json
{
  "result": true,
  "code": 0,
  "message": "",
  "data": [
    {
      "repository_name": "2_bklog_demo",
      "alias": "demo",
      "cluster_id": 6,
      "cluster_name": "es-6",
      "display_name": "集群 6",
      "create_time": "2026-11-09 10:00:00",
      "type": "cos"
    }
  ]
}
```

## 注意事项

- 需要具备该业务的查看权限。
- 该集群下没有可用仓库时返回空列表。
- 返回结果中的 `repository_name` 可作为创建或更新采集项归档时的快照仓库名。
- 仓库的详细配置（`settings`）不在返回范围内。
