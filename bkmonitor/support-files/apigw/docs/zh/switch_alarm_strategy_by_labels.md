### 功能描述

根据标签批量启停告警策略

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段        | 类型          | 必选  | 描述                  |
| --------- | ----------- | --- | ------------------- |
| bk_biz_id | int         | 是   | 业务 ID                |
| labels    | List\[str\] | 是   | 标签列表                |
| action    | str         | 是   | 操作类型\["on", "off"\] |
| force     | bool        | 否   | 是否强制操作, 默认为 false   |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "labels": ["bk-monitor"],
  "action": "on"
}
```

### 返回结果

| 字段      | 类型          | 描述     |
| ------- | ----------- | ------ |
| result  | bool        | 请求是否成功 |
| code    | int         | 返回的状态码 |
| message | string      | 描述信息   |
| data    | List\[int\] | 策略 ID 列表 |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [280]
}
```
