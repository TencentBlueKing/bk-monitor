### 功能描述

获取报表变量

### 请求参数

| 字段       | 类型  | 必选 | 描述   |
|----------|-----|----|------|
| scenario | str | 是  | 订阅场景 |

### 请求参数示例

```json
{
  "scenario": "clustering"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 变量列表   |

#### data 元素字段说明

| 字段          | 类型   | 描述   |
|-------------|------|------|
| name        | str  | 变量名称 |
| description | str  | 变量描述 |
| example     | str  | 示例值  |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "name": "time",
      "description": "系统时间",
      "example": "2023-12-12 22:00"
    },
    {
      "name": "index_set_name",
      "description": "索引集名称",
      "example": "apm_demo_app_1111"
    },
    {
      "name": "business_name",
      "description": "业务名称",
      "example": "测试业务"
    }
  ]
}
```
