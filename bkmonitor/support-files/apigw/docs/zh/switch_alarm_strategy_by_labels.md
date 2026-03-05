### 功能描述

根据标签批量启停告警策略


### 请求参数

| 字段        | 类型          | 必选  | 描述                  |
| --------- | ----------- | --- | ------------------- |
| bk_biz_id | int         | 是   | 业务ID                |
| labels    | list[str] | 是   | 标签列表                |
| action    | str         | 是   | 操作类型，可选值：`on`（启用）、`off`（停用） |
| force     | bool        | 否   | 是否强制操作，默认为false。如果为false，则只操作未被修改过的策略（创建时间和更新时间差小于等于1秒）   |

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "labels": ["bk-monitor"],
  "action": "on"
}
```

### 响应参数

| 字段      | 类型          | 描述     |
| ------- | ----------- | ------ |
| result  | bool        | 请求是否成功 |
| code    | int         | 返回的状态码 |
| message | string      | 描述信息   |
| data    | list[int] | 成功启停的策略ID列表 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [280]
}
```
