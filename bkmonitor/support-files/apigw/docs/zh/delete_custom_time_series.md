### 功能描述

删除自定义时序


#### 接口参数

| 字段                   | 类型  | 必选 | 描述      |
|----------------------|-----|----|---------|
| time_series_group_id | int | 是  | 自定义时序ID |

#### 请求示例

```json
{
  "time_series_group_id": 33
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 响应数据   |

#### data 响应数据

| 字段                   | 类型  | 描述      |
|----------------------|-----|---------|
| time_series_group_id | int | 自定义时序ID |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "time_series_group_id": 33
  }
}
```

