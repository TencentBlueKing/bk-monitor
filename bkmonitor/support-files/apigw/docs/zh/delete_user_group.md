### 功能描述

删除通知组（告警组）

**注意事项：**

- 只能删除未被策略关联的告警组
- 如果告警组已被策略关联，将返回错误信息
- 删除告警组时会同时删除关联的轮值安排（DutyArrange）

### 请求参数

| 字段         | 类型        | 必选 | 描述             |
|------------|-----------|----|----------------|
| bk_biz_ids | list[int] | 是  | 业务ID列表         |
| ids        | list[int] | 是  | 告警组ID列表，支持批量删除 |

### 请求参数示例

#### 示例1：删除单个告警组

```json
{
  "bk_biz_ids": [2],
  "ids": [1]
}
```

#### 示例2：批量删除多个告警组

```json
{
  "bk_biz_ids": [2],
  "ids": [1, 2, 3]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | object | 返回数据   |

#### data 字段说明

| 字段  | 类型        | 描述           |
|-----|-----------|--------------|
| ids | list[int] | 成功删除的告警组ID列表 |

### 响应参数示例

#### 成功响应

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "ids": [1, 2, 3]
  }
}
```

#### 失败响应（告警组已被策略关联）

```json
{
  "result": false,
  "code": 400,
  "message": "Follow groups(1,2) are to not allowed to delete because of these user groups have been related to some strategies",
  "data": null
}
```
