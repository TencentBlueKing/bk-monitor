### 功能描述

导入 AsCode 配置

### 请求参数

| 字段      | 类型      | 必选 | 描述                  |
|---------|---------|----|---------------------|
| bk_biz_id | int | 否  | 业务ID，与space_uid至少需要提供一个 |
| space_uid | str | 否  | 空间UID，与bk_biz_id至少需要提供一个 |
| configs | dict    | 是  | 文件内容，key为文件路径，value为文件内容字符串 |
| app     | str  | 否  | 配置分组，默认as_code       |
| overwrite | bool    | 否  | 是否跨分组覆盖同名配置，默认false |
| incremental | bool | 否 | 是否增量导入，默认false |

**参数约束：**
- `bk_biz_id` 和 `space_uid` 至少需要提供一个
- 如果只提供 `space_uid`，系统会自动转换为对应的 `bk_biz_id`

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "configs": {
      "rule/xxx.yaml": "xxxx",
      "notice/xxx.yaml": "xxxx"
    },
    "app": "as_code",
    "overwrite": false,
    "incremental": false
}
```

### 响应参数

| 字段      | 类型     | 描述       |
|---------|--------|----------|
| result  | bool   | 请求是否成功   |
| code    | int    | 返回的状态码   |
| message | string | 描述信息     |
| data    | dict   | 导入结果数据   |

#### data字段说明

| 字段      | 类型        | 描述                           |
|---------|-----------|------------------------------|
| result  | bool      | 导入是否成功                       |
| message | string    | 导入描述信息，失败时包含错误数量信息           |
| data    | dict/null | 导入返回数据，成功时为空字典，失败时为null     |
| errors  | dict      | 错误信息，key为配置文件路径，value为错误详情 |

### 响应参数示例

**成功响应：**
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "result": true,
        "message": "",
        "data": {},
        "errors": {}
    }
}
```

**失败响应：**
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "result": false,
        "message": "2 configs import failed",
        "data": null,
        "errors": {
            "rule/xxx.yaml": "配置解析失败: 缺少必填字段",
            "notice/yyy.yaml": "告警组不存在"
        }
    }
}
```
