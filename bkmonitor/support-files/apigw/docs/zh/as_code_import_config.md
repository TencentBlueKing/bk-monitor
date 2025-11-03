### 功能描述

导入 AsCode 配置

### 请求参数

| 字段      | 类型      | 必选 | 描述                  |
|---------|---------|----|---------------------|
| configs | dict    | 是  | yaml配置              |
| app     | string  | 否  | 配置分组，默认defult       |
| bk_biz_id | integer | 是  | 业务ID                |
| overwrite | dict    | 否  | 是否跨分组覆盖同名配置，默认false |

### 请求参数示例

```json
{
    "configs": {
      "rule/xxx.yaml": "xxxx",
      "notice/xxx.yaml": "xxxx"
    },
    "app": "default",
    "bk_biz_id": 2,
    "overwrite": false
}
```

### 响应参数

| 字段    | 类型        | 描述         |
| ------- |-----------| ------------ |
| result  | bool      | 请求是否成功 |
| message | string    | 描述信息     |
| data    | dict/null | 返回数据     |

### 响应参数示例

```json
{
    "message": "",
    "data": {},
    "result": true
}
```
