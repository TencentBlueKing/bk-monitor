### 功能描述

导入策略到 APM 服务

### 请求参数

| 字段名              | 类型        | 是否必选 | 描述           |
|------------------|-----------|------|--------------|
| bk_biz_id        | int       | 否    | 业务ID         |
| space_uid        | str       | 否    | 空间唯一标识       |
| app_name         | str       | 是    | 应用名称         |
| group_type       | str       | 是    | 策略组类型        |
| apply_types      | list[str] | 否    | 策略类型列表       |
| apply_services   | list[str] | 否    | 服务列表         |
| notice_group_ids | list[int] | 否    | 告警组 ID 列表    |
| config           | str       | 否    | 配置文本（JSON格式） |

**注意事项：**

- `bk_biz_id` 和 `space_uid` 至少需要传其中一个
- 如果传递 `space_uid`，系统会自动转换为对应的 `bk_biz_id`
- `config` 参数必须是合法的 JSON 字符串

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "app_name": "my_app",
  "group_type": "rpc",
  "apply_types": ["error_rate", "response_time"],
  "apply_services": ["service_a", "service_b"],
  "notice_group_ids": [123, 456],
  "config": "{\"threshold\": 0.1, \"duration\": 5000}"
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {}
}
```
